# FitNut

FitNut lets you create an account, log in, and save food, activity, and sleep records. Each user sees their own records. Admins can view users, change their account type, or suspend an account.

Python and Flask run the website. MySQL stores the accounts and records.

## First time setup on Windows

1. Install Python or newer and MySQL Server.
2. Open PowerShell inside the `FitNut` folder.
3. Run:

```powershell
.\scripts\setup-mysql.ps1
.\scripts\run.ps1
```

Setup creates the database, makes the local database passwords, and installs the Python packages the app needs. If it cannot find MySQL, check the installation path near the top of `scripts/mysql-common.ps1`.

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser. Keep the PowerShell window open while using the app.

## Use the website

1. Choose **Create account**. Enter your first name, last name, email, and password.
2. Log in with your email and password.
3. Open **Food**, **Activity**, or **Sleep** to add, edit, or delete records.
4. Choose **Log out** when finished.

On **Food**, choose **New meal**, or select a saved meal to add another food to it. Enter the amount and unit, such as 1 cup. Nutrition values are optional and apply to the whole food entry.

On **Activity**, enter the start time and duration. The app works out the finish time. Enter calories yourself if you know them.

**Overview** shows how many records you have saved. Food search, automatic calorie estimates, AI plans, and dashboard charts have not been added.

## Make an admin account

While MySQL is running, open another PowerShell window in `FitNut` and run:

```powershell
.\.venv\Scripts\python.exe .\scripts\create_admin.py
```

Choose a new admin's first name, last name, email, and password. Log in with those details, then open **Users**. Admin accounts use the same login page as regular users.

## Database and files

The [database guide](database/README.md) explains the nine tables and how they connect. The setup starts EMPTY.

Database connection details are saved privately in `.env.local`. This file and the saved database records are not included in GitHub uploads. Passwords are stored as  hashes not readable text.

| File or folder | What it does |
| --- | --- |
| `app.py` | Opens the website pages |
| `accounts.py` | Handles accounts, login, logout, and admin actions |
| `logs.py` and `log_data.py` | Check, save, and read food, activity, and sleep records |
| `db.py` | Connects to MySQL and runs database commands |
| `templates` | Contains the pages |
| `static` | Contains page styles and button/form behavior |
| `scripts` | Contains setup and start/stop commands |
