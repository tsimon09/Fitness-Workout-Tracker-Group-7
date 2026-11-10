# Fitness Workout Tracker - Group 7

FitNut lets users create an account, log in, and save food, activity, and sleep records. The pages are kept simple for the Sprint 2 demo.

## Start the app

Open the [FitNut guide](FitNut/README.md) for the setup commands, website instructions, and how to make an admin account. You need Python 3.12 or newer and MySQL Server on Windows.

## Database

The app uses one combined database design. It keeps the team's separate tables for meals, foods, units, activity types, and recorded activities. It also keeps the working account and login features, plus sleep records.

The app's SQL files are in `FitNut/database`. The [database guide](FitNut/database/README.md) explains what each table stores.

The original `fitness_tracker_schema.sql` file is kept unchanged as a reference. The app's setup does not run that file.

## Branch

This work is on `sprint2-fitnut-app` for the team to review. It has not been merged into `main`.

Passwords, saved database records, and local test files are kept out of new commits.
