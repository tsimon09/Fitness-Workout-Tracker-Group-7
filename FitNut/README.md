# FitNut

Flask and MySQL app for food, activity, and sleep logs.

## Run

Install Python 3.12+ and MySQL 8.0.16+. In PowerShell, open this folder and run:

```powershell
.\scripts\setup-mysql.ps1
.\scripts\run.ps1
```

Open [localhost:5000](http://127.0.0.1:5000), create an account, and log in. If MySQL isn't found, update its path in `scripts/mysql-common.ps1`.

Food search uses USDA. Choose a result and enter grams or servings, or enter a food manually. Add foods to the meal, then save. Manual nutrition values are for the whole entry.

Activity logging estimates calories for walking, running, cycling, and swimming using weight, duration, and intensity. Other activities accept manual calories. Review before saving.

AI plans haven't been added yet.

## Database

[Tables and relationships](database/SCHEMA.md). Setup applies the SQL files and migrations; rerun it when updating. Existing records in the current schema are kept. Back up a shared database first.

Connection settings go in `.env.local`. Food search accepts `USDA_API_KEY`; otherwise it uses the limited demo key. Keep credentials out of Git.

## Tests

```powershell
.\scripts\test.ps1
```

Tests use a temporary database. The optional browser test is `tests/browser_smoke.cjs` and requires Playwright and a running app.

To create an admin account, run `.\.venv\Scripts\python.exe .\scripts\create_admin.py` while MySQL is running.
