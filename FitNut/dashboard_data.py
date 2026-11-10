
"""Database-backed dashboard summaries for FitNut."""

from datetime import date, datetime, time, timedelta

from flask import g

from db import fetch_one, fetch_all


def _num(value):
    return float(value or 0)


def _bounds(period, selected):
    if period == "week":
        start = selected - timedelta(days=selected.weekday())
        end = start + timedelta(days=7)
    elif period == "month":
        start = selected.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        start = selected
        end = start + timedelta(days=1)

    return start, end


def dashboard_summary(period="day", selected=None):
    if period not in ("day", "week", "month"):
        raise ValueError("Choose a valid dashboard period")

    selected = selected or date.today()
    start, end = _bounds(period, selected)

    user_id = g.user["user_id"]

    args = (
        user_id,
        datetime.combine(start, time.min),
        datetime.combine(end, time.min),
    )

    food = fetch_one(
        """
        SELECT
            COUNT(*) AS entries,
            COUNT(f.calories) AS calorie_entries,
            COALESCE(SUM(f.calories), 0) AS calories,
            COALESCE(SUM(f.protein_g), 0) AS protein,
            COALESCE(SUM(f.carbs_g), 0) AS carbs,
            COALESCE(SUM(f.fat_g), 0) AS fat
        FROM food_entries f
        JOIN eating_events e
          ON e.eating_event_id = f.eating_event_id
        WHERE e.user_id = %s
          AND e.event_datetime >= %s
          AND e.event_datetime < %s
        """,
        args,
    )

    activity = fetch_one(
        """
        SELECT
            COUNT(*) AS entries,
            COUNT(calories_burned) AS calorie_entries,
            COALESCE(SUM(calories_burned), 0) AS calories,
            COALESCE(
                SUM(
                    TIMESTAMPDIFF(
                        SECOND,
                        time_started,
                        time_finished
                    )
                ) / 60,
                0
            ) AS minutes
        FROM activity_events
        WHERE user_id = %s
          AND time_started >= %s
          AND time_started < %s
        """,
        args,
    )

    sleep = fetch_one(
        """
        SELECT
            COUNT(*) AS entries,
            COALESCE(
                SUM(
                    TIMESTAMPDIFF(
                        SECOND,
                        sleep_start,
                        sleep_end
                    )
                ) / 3600,
                0
            ) AS hours,
            AVG(sleep_quality) AS quality
        FROM sleep_logs
        WHERE user_id = %s
          AND sleep_start >= %s
          AND sleep_start < %s
        """,
        args,
    )

    food_days = fetch_all(
        """
        SELECT
            DATE(e.event_datetime) AS day,
            SUM(f.calories) AS calories
        FROM food_entries f
        JOIN eating_events e
          ON e.eating_event_id = f.eating_event_id
        WHERE e.user_id = %s
          AND e.event_datetime >= %s
          AND e.event_datetime < %s
        GROUP BY DATE(e.event_datetime)
        ORDER BY day
        """,
        args,
    )

    activity_days = fetch_all(
        """
        SELECT
            DATE(time_started) AS day,
            SUM(
                TIMESTAMPDIFF(
                    SECOND,
                    time_started,
                    time_finished
                )
            ) / 60 AS minutes
        FROM activity_events
        WHERE user_id = %s
          AND time_started >= %s
          AND time_started < %s
        GROUP BY DATE(time_started)
        ORDER BY day
        """,
        args,
    )

    food_by_day = {
        row["day"]: _num(row["calories"])
        for row in food_days
    }

    activity_by_day = {
        row["day"]: _num(row["minutes"])
        for row in activity_days
    }

    days = []
    cursor = start

    while cursor < end:
        days.append({
            "date": cursor.isoformat(),
            "label": cursor.strftime("%b %d"),
            "calories": round(
                food_by_day.get(cursor, 0), 1
            ),
            "minutes": round(
                activity_by_day.get(cursor, 0), 1
            ),
        })

        cursor += timedelta(days=1)

    max_calories = max(
        (item["calories"] for item in days),
        default=0,
    ) or 1

    max_minutes = max(
        (item["minutes"] for item in days),
        default=0,
    ) or 1

    for item in days:
        item["calories_level"] = min(
            20,
            round(20 * item["calories"] / max_calories),
        )

        item["minutes_level"] = min(
            20,
            round(20 * item["minutes"] / max_minutes),
        )

    return {
        "period": period,
        "selected": selected.isoformat(),
        "start": start.isoformat(),
        "end": (
            end - timedelta(days=1)
        ).isoformat(),
        "food": {
            key: (
                int(value)
                if key.endswith("entries")
                else round(_num(value), 1)
            )
            for key, value in food.items()
        },
        "activity": {
            key: (
                int(value)
                if key.endswith("entries")
                else round(_num(value), 1)
            )
            for key, value in activity.items()
        },
        "sleep": {
            "entries": int(sleep["entries"]),
            "hours": round(
                _num(sleep["hours"]), 1
            ),
            "quality": (
                round(
                    _num(sleep["quality"]), 1
                )
                if sleep["quality"] is not None
                else None
            ),
        },
        "days": days,
    }
