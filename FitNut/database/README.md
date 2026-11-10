# FitNut database

The app uses one combined database design. The SQL files create nine tables, and the website saves records in those tables.

## What each table stores

| Original table | App table | What it stores |
| --- | --- | --- |
| `AppUser` | `users` | First name, last name, email, protected password, account type, account status, created date, and last online |
| `UserSession` | `sessions` | A protected sign-in code and when that login starts, expires, or ends |
| `ActivityType` | `activity_types` | Activity choices  |
| `ActivityEvent` | `activity_events` |  user activity times, calories, and notes |
| `MealType` | `meal_types` | Breakfast, lunch, dinner, and snack |
| `EatingEvent` | `eating_events` |  user meal, when they ate, and meal notes |
| `UnitOfMeasure` | `units_of_measure` | Amount units such as g, cup, and serving |
| `FoodEntry` | `food_entries` | Foods in a meal, amounts, units, and optional nutrition values |
| Added from the working app | `sleep_logs` | Sleep start/end times, an optional 1-5 rating, and notes |

## How they connect

A user can have many meals. Each meal can contain several food entries. For example, one breakfast can contain oatmeal and an apple. Each food entry points to its meal and its amount unit.

A recorded activity points to the user who added it and an activity type. Sleep records and logins also point to their user.

Each table has an ID number to identify its records. Related tables store that number to connect the records. In SQL, these are called **primary keys** and **foreign keys**.

Registration uses first name, last name, email, and password. Email is used for login, so there is no separate username. Account types are `user` and `admin`; an account can be `active` or `suspended`.

## SQL files

- `schema.sql` creates the database and the `users` table.
- `other-tables.sql` creates the other eight tables.
- `scripts/init_database.py` reads both files and adds the starting meal, unit, and activity choices.

The original `fitness_tracker_schema.sql` file at the top of the repository stays unchanged as a reference. The app's setup uses the two SQL files in this folder.

## Starting fresh

For a new local installation, follow the [FitNut setup instructions](../README.md#first-time-setup-on-windows). There is no old-record copying step.

If you already used the older database design, setup stops when it finds the older user table. Use a new empty database and set `MYSQL_DATABASE` in your private `.env.local` to its name. Then run `scripts/init_database.py` with a database account allowed to create tables.

The SQL files use the name `fitnut`. The app uses the database named in `.env.local`, so the name can differ on another computer or hosting site. The table design stays the same.

Running setup again on the new design keeps records already saved there.
