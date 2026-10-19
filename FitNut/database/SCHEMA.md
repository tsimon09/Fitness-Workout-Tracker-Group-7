# Database tables

Tables used by the app. Refresh with `scripts/export_schema.py` after running setup.

PK = primary key; FK = foreign key. Dates are stored in UTC. NULL means no value was entered.

## users

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `user_id` | `int` | NO | PK | —; auto_increment |
| `first_name` | `varchar(50)` | NO | — | — |
| `last_name` | `varchar(50)` | NO | — | — |
| `email` | `varchar(254)` | NO | UNIQUE | — |
| `password_hash` | `varchar(255)` | NO | — | — |
| `role` | `enum('user','admin')` | NO | — | user |
| `status` | `enum('active','suspended')` | NO | — | active |
| `created_at` | `datetime` | NO | — | CURRENT_TIMESTAMP; DEFAULT_GENERATED |
| `last_online` | `datetime` | YES | — | NULL |

Indexes: `email` (email) UNIQUE; `PRIMARY` (user_id) UNIQUE.

## sessions

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `session_id` | `int` | NO | PK | —; auto_increment |
| `user_id` | `int` | NO | FK → `users.user_id`; delete CASCADE | — |
| `token_hash` | `char(64)` | NO | UNIQUE | — |
| `created_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |
| `expires_at` | `datetime(6)` | NO | — | — |
| `revoked_at` | `datetime(6)` | YES | — | NULL |

Indexes: `idx_sessions_user` (user_id); `PRIMARY` (session_id) UNIQUE; `token_hash` (token_hash) UNIQUE.

- `chk_sessions_expiration`: ``(`expires_at` > `created_at`)``
- `chk_sessions_revocation`: ``((`revoked_at` is null) or (`revoked_at` >= `created_at`))``

## user_profiles

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `user_id` | `int` | NO | PK; FK → `users.user_id`; delete CASCADE | — |
| `weight_kg` | `decimal(5,2)` | YES | — | NULL |
| `updated_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |
| `daily_calorie_target` | `decimal(10,2)` | YES | — | NULL |
| `weekly_activity_minutes` | `decimal(10,2)` | YES | — | NULL |
| `age` | `tinyint unsigned` | YES | — | NULL |
| `height_cm` | `decimal(5,2)` | YES | — | NULL |
| `fitness_goal` | `enum('maintain','lose_weight','gain_muscle','improve_fitness')` | YES | — | NULL |
| `fitness_level` | `enum('beginner','intermediate','advanced')` | YES | — | NULL |
| `dietary_pattern` | `enum('no_preference','vegetarian','vegan','pescatarian')` | YES | — | NULL |
| `allergy_status` | `enum('not_provided','none_reported','listed')` | NO | — | not_provided |

Indexes: `PRIMARY` (user_id) UNIQUE.

- `chk_daily_target`: ``((`daily_calorie_target` is null) or (`daily_calorie_target` > 0))``
- `chk_profile_age`: ``((`age` is null) or (`age` between 1 and 120))``
- `chk_profile_height`: ``((`height_cm` is null) or ((`height_cm` > 0) and (`height_cm` <= 300)))``
- `chk_profile_weight`: ``(`weight_kg` > 0)``
- `chk_weekly_target`: ``((`weekly_activity_minutes` is null) or (`weekly_activity_minutes` > 0))``

## user_restrictions

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `restriction_id` | `int` | NO | PK | —; auto_increment |
| `user_id` | `int` | NO | FK → `users.user_id`; delete CASCADE | — |
| `kind` | `enum('allergy','intolerance','preference')` | NO | — | — |
| `code` | `varchar(100)` | NO | — | — |
| `label` | `varchar(100)` | NO | — | — |

Indexes: `PRIMARY` (restriction_id) UNIQUE; `uq_user_restriction` (user_id,kind,code) UNIQUE.

- `chk_restriction_label`: ``(char_length(trim(`label`)) > 0)``

## meal_types

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `meal_type_id` | `int` | NO | PK | —; auto_increment |
| `meal_type` | `varchar(20)` | NO | UNIQUE | — |

Indexes: `meal_type` (meal_type) UNIQUE; `PRIMARY` (meal_type_id) UNIQUE.

## eating_events

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `eating_event_id` | `int` | NO | PK | —; auto_increment |
| `user_id` | `int` | NO | FK → `users.user_id`; delete CASCADE | — |
| `meal_type_id` | `int` | NO | FK → `meal_types.meal_type_id`; delete NO ACTION | — |
| `event_datetime` | `datetime(6)` | NO | — | — |
| `comments` | `text` | YES | — | NULL |

Indexes: `fk_eating_events_meal` (meal_type_id); `PRIMARY` (eating_event_id) UNIQUE; `uq_eating_events` (user_id,meal_type_id,event_datetime) UNIQUE.

## units_of_measure

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `unit_id` | `int` | NO | PK | —; auto_increment |
| `unit_name` | `varchar(30)` | NO | UNIQUE | — |
| `unit_abbreviation` | `varchar(10)` | YES | — | NULL |

Indexes: `PRIMARY` (unit_id) UNIQUE; `unit_name` (unit_name) UNIQUE.

## food_catalog

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `food_id` | `int` | NO | PK | —; auto_increment |
| `fdc_id` | `int` | NO | UNIQUE | — |
| `food_name` | `varchar(150)` | NO | — | — |
| `calories` | `decimal(10,2)` | YES | — | NULL |
| `protein_g` | `decimal(10,2)` | YES | — | NULL |
| `carbs_g` | `decimal(10,2)` | YES | — | NULL |
| `fat_g` | `decimal(10,2)` | YES | — | NULL |
| `fiber_g` | `decimal(10,2)` | YES | — | NULL |
| `cached_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |

Indexes: `fdc_id` (fdc_id) UNIQUE; `PRIMARY` (food_id) UNIQUE.

- `chk_catalog_nutrition`: ``(((`calories` is null) or (`calories` >= 0)) and ((`protein_g` is null) or (`protein_g` >= 0)) and ((`carbs_g` is null) or (`carbs_g` >= 0)) and ((`fat_g` is null) or (`fat_g` >= 0)) and ((`fiber_g` is null) or (`fiber_g` >= 0)))``

## food_entries

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `food_entry_id` | `int` | NO | PK | —; auto_increment |
| `eating_event_id` | `int` | NO | FK → `eating_events.eating_event_id`; delete CASCADE | — |
| `unit_id` | `int` | NO | FK → `units_of_measure.unit_id`; delete NO ACTION | — |
| `food_name` | `varchar(150)` | NO | — | — |
| `quantity` | `decimal(10,3)` | NO | — | — |
| `calories` | `decimal(10,2)` | YES | — | NULL |
| `protein_g` | `decimal(10,2)` | YES | — | NULL |
| `carbs_g` | `decimal(10,2)` | YES | — | NULL |
| `fat_g` | `decimal(10,2)` | YES | — | NULL |
| `fiber_g` | `decimal(10,2)` | YES | — | NULL |
| `created_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |
| `food_id` | `int` | YES | FK → `food_catalog.food_id`; delete SET NULL | NULL |
| `serving_grams` | `decimal(10,3)` | YES | — | NULL |

Indexes: `fk_food_catalog` (food_id); `fk_food_entries_event` (eating_event_id); `fk_food_entries_unit` (unit_id); `PRIMARY` (food_entry_id) UNIQUE.

- `chk_food_entries_calories`: ``((`calories` is null) or (`calories` >= 0))``
- `chk_food_entries_carbs`: ``((`carbs_g` is null) or (`carbs_g` >= 0))``
- `chk_food_entries_fat`: ``((`fat_g` is null) or (`fat_g` >= 0))``
- `chk_food_entries_fiber`: ``((`fiber_g` is null) or (`fiber_g` >= 0))``
- `chk_food_entries_name`: ``(char_length(trim(`food_name`)) > 0)``
- `chk_food_entries_protein`: ``((`protein_g` is null) or (`protein_g` >= 0))``
- `chk_food_entries_quantity`: ``(`quantity` > 0)``
- `chk_food_serving`: ``((`serving_grams` is null) or (`serving_grams` > 0))``

## activity_types

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `activity_type_id` | `int` | NO | PK | —; auto_increment |
| `activity_name` | `varchar(100)` | NO | UNIQUE | — |

Indexes: `activity_name` (activity_name) UNIQUE; `PRIMARY` (activity_type_id) UNIQUE.

## activity_events

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `activity_event_id` | `int` | NO | PK | —; auto_increment |
| `user_id` | `int` | NO | FK → `users.user_id`; delete CASCADE | — |
| `activity_type_id` | `int` | NO | FK → `activity_types.activity_type_id`; delete NO ACTION | — |
| `custom_activity_name` | `varchar(100)` | YES | — | NULL |
| `time_started` | `datetime(6)` | NO | — | — |
| `time_finished` | `datetime(6)` | NO | — | — |
| `calories_burned` | `decimal(10,2)` | YES | — | NULL |
| `notes` | `text` | YES | — | NULL |
| `created_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |
| `intensity` | `enum('low','moderate','high')` | YES | — | NULL |
| `distance_km` | `decimal(10,3)` | YES | — | NULL |
| `set_count` | `int` | YES | — | NULL |
| `rep_count` | `int` | YES | — | NULL |
| `calorie_source` | `enum('manual','estimated')` | NO | — | manual |
| `body_weight_kg` | `decimal(5,2)` | YES | — | NULL |
| `met_value` | `decimal(4,2)` | YES | — | NULL |

Indexes: `fk_activity_events_type` (activity_type_id); `idx_activity_events_user_date` (user_id,time_started); `PRIMARY` (activity_event_id) UNIQUE.

- `chk_activity_distance`: ``((`distance_km` is null) or (`distance_km` >= 0))``
- `chk_activity_events_calories`: ``((`calories_burned` is null) or (`calories_burned` >= 0))``
- `chk_activity_events_time`: ``(`time_finished` > `time_started`)``
- `chk_activity_met`: ``((`met_value` is null) or (`met_value` > 0))``
- `chk_activity_reps`: ``((`rep_count` is null) or (`rep_count` > 0))``
- `chk_activity_sets`: ``((`set_count` is null) or (`set_count` > 0))``
- `chk_activity_weight`: ``((`body_weight_kg` is null) or (`body_weight_kg` > 0))``

## sleep_logs

| Column | MySQL type | Nullable | Key / relationship | Default / extra |
| --- | --- | --- | --- | --- |
| `sleep_log_id` | `int` | NO | PK | —; auto_increment |
| `user_id` | `int` | NO | FK → `users.user_id`; delete CASCADE | — |
| `sleep_start` | `datetime(6)` | NO | — | — |
| `sleep_end` | `datetime(6)` | NO | — | — |
| `sleep_quality` | `tinyint unsigned` | YES | — | NULL |
| `notes` | `text` | YES | — | NULL |
| `created_at` | `datetime(6)` | NO | — | CURRENT_TIMESTAMP(6); DEFAULT_GENERATED |

Indexes: `idx_sleep_logs_user_date` (user_id,sleep_start); `PRIMARY` (sleep_log_id) UNIQUE.

- `chk_sleep_dates`: ``(`sleep_end` > `sleep_start`)``
- `chk_sleep_quality`: ``((`sleep_quality` is null) or (`sleep_quality` between 1 and 5))``
