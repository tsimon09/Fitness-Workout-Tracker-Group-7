
"""FitNut exercise library: exercise reference content."""

from urllib.parse import quote_plus

from flask import Blueprint, render_template, request

from accounts import login_required


exercise_library = Blueprint("exercise_library", __name__)


def exercise(slug, name, muscle, difficulty, equipment, steps, tips):
    return {
        "slug": slug,
        "name": name,
        "muscle": muscle,
        "difficulty": difficulty,
        "equipment": equipment,
        "steps": steps,
        "tips": tips,
        "video_url": (
            "https://www.youtube.com/results?search_query="
            + quote_plus(name + " exercise proper form demonstration")
        ),
    }


EXERCISES = [
    exercise(
        "squat", "Bodyweight Squat", "Legs", "Beginner", "None",
        [
            "Stand with your feet approximately shoulder-width apart.",
            "Brace your core and keep your chest upright.",
            "Bend your hips and knees to lower your body.",
            "Lower as far as you can while maintaining control.",
            "Push through your feet to return to standing.",
        ],
        "Keep your knees tracking in the same direction as your toes.",
    ),
    exercise(
        "push-up", "Push-Up", "Chest", "Beginner", "None",
        [
            "Place your hands slightly wider than shoulder-width.",
            "Extend your legs and maintain a straight body line.",
            "Lower your chest toward the floor with control.",
            "Keep your elbows at a comfortable angle.",
            "Push back up without letting your hips sag.",
        ],
        "Use an elevated surface or your knees for an easier variation.",
    ),
    exercise(
        "plank", "Forearm Plank", "Core", "Beginner", "None",
        [
            "Place your forearms on the floor beneath your shoulders.",
            "Extend your legs behind you.",
            "Brace your abdomen and glutes.",
            "Maintain a straight line from head to heels.",
            "Breathe normally while holding the position.",
        ],
        "Stop when you can no longer maintain a neutral back.",
    ),
    exercise(
        "lunge", "Reverse Lunge", "Legs", "Beginner", "None",
        [
            "Stand upright with your feet hip-width apart.",
            "Step one foot backward.",
            "Bend both knees while keeping your torso upright.",
            "Push through your front foot to return to standing.",
            "Repeat on the opposite side.",
        ],
        "Start with a short, controlled range of motion.",
    ),
    exercise(
        "glute-bridge", "Glute Bridge", "Glutes", "Beginner", "None",
        [
            "Lie on your back with your knees bent.",
            "Place your feet flat on the floor.",
            "Brace your abdomen.",
            "Push through your heels and raise your hips.",
            "Pause briefly, then lower your hips slowly.",
        ],
        "Avoid excessively arching your lower back.",
    ),
    exercise(
        "jumping-jack", "Jumping Jack", "Cardio", "Beginner", "None",
        [
            "Stand with your arms at your sides.",
            "Jump your feet apart while raising your arms overhead.",
            "Land softly with slightly bent knees.",
            "Jump back to the starting position.",
            "Continue at a comfortable pace.",
        ],
        "Step one foot out at a time for a lower-impact variation.",
    ),
    exercise(
        "dumbbell-row", "One-Arm Dumbbell Row", "Back",
        "Intermediate", "Dumbbell",
        [
            "Support one hand on a stable bench or surface.",
            "Hold a dumbbell in the opposite hand.",
            "Keep your back neutral and core engaged.",
            "Pull the dumbbell toward your hip.",
            "Lower the weight slowly and repeat.",
        ],
        "Avoid twisting your torso to lift the weight.",
    ),
    exercise(
        "shoulder-press", "Dumbbell Shoulder Press", "Shoulders",
        "Intermediate", "Dumbbells",
        [
            "Sit or stand with a dumbbell in each hand.",
            "Hold the weights near shoulder height.",
            "Brace your core.",
            "Press the weights overhead with control.",
            "Lower them slowly to the starting position.",
        ],
        "Use a weight that does not force you to arch your back.",
    ),
    exercise(
        "biceps-curl", "Dumbbell Biceps Curl", "Arms",
        "Beginner", "Dumbbells",
        [
            "Stand upright with a dumbbell in each hand.",
            "Keep your elbows close to your sides.",
            "Bend your elbows to raise the weights.",
            "Pause briefly near the top.",
            "Lower the weights without swinging.",
        ],
        "Keep your upper arms relatively still.",
    ),
    exercise(
        "deadlift", "Romanian Deadlift", "Legs",
        "Intermediate", "Dumbbells",
        [
            "Stand tall holding dumbbells in front of your thighs.",
            "Keep a slight bend in your knees.",
            "Push your hips backward while keeping your back neutral.",
            "Lower the weights along your legs within a controlled range.",
            "Drive your hips forward to return to standing.",
        ],
        "Prioritize the hip-hinge movement over lifting heavy weights.",
    ),
    exercise(
        "mountain-climber", "Mountain Climber", "Cardio",
        "Intermediate", "None",
        [
            "Begin in a high plank position.",
            "Brace your core and keep your shoulders over your hands.",
            "Bring one knee toward your chest.",
            "Return that leg and alternate sides.",
            "Increase your pace only while maintaining control.",
        ],
        "Keep your hips stable instead of bouncing excessively.",
    ),
    exercise(
        "side-plank", "Side Plank", "Core",
        "Intermediate", "None",
        [
            "Lie on one side with your elbow below your shoulder.",
            "Stack or stagger your feet.",
            "Lift your hips off the floor.",
            "Maintain a straight line through your body.",
            "Lower carefully and repeat on the other side.",
        ],
        "Try keeping your lower knee on the floor for support.",
    ),
]


MUSCLES = sorted({item["muscle"] for item in EXERCISES})
DIFFICULTIES = ["Beginner", "Intermediate"]


@exercise_library.get("/exercises")
@login_required(html=True)
def exercise_list():
    search = request.args.get("q", "").strip()[:100]
    muscle = request.args.get("muscle", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    selected_slug = request.args.get("exercise", "").strip()

    if muscle not in MUSCLES:
        muscle = ""

    if difficulty not in DIFFICULTIES:
        difficulty = ""

    filtered = []

    for item in EXERCISES:
        matches_search = (
            not search
            or search.casefold() in item["name"].casefold()
            or search.casefold() in item["muscle"].casefold()
            or search.casefold() in item["equipment"].casefold()
        )

        matches_muscle = not muscle or item["muscle"] == muscle
        matches_difficulty = (
            not difficulty or item["difficulty"] == difficulty
        )

        if matches_search and matches_muscle and matches_difficulty:
            filtered.append(item)

    selected = next(
        (item for item in EXERCISES if item["slug"] == selected_slug),
        None,
    )

    return render_template(
        "exercises.html",
        exercises=filtered,
        selected=selected,
        search=search,
        muscle=muscle,
        difficulty=difficulty,
        muscles=MUSCLES,
        difficulties=DIFFICULTIES,
        total=len(EXERCISES),
    )
