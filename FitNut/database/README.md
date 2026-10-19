# Database

[Table definitions](SCHEMA.md) list the columns, types, and keys.

Meals belong to users and contain food entries. Foods link to a unit and optionally a USDA food record. Activities belong to users and link to an activity type. Profiles hold weight and logging targets.

Setup runs `schema.sql`, `other-tables.sql`, and the numbered migrations through `scripts/init_database.py`. Run the normal setup script again to apply updates. The top-level `fitness_tracker_schema.sql` is the older design.

If setup finds the older user-table format, use a separate empty database; it doesn't convert old records. Back up an existing database before updating it. Initialization needs CREATE/ALTER permissions; the app only needs read/write access.

Refresh the table reference from the `FitNut` folder:

```powershell
.\.venv\Scripts\python.exe .\scripts\export_schema.py
```
