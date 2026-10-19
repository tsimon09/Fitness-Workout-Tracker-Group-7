"""Create a new administrator. Passwords are entered locally and are not printed."""
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mysql.connector
from app import app
from db import execute, get_db
from werkzeug.security import generate_password_hash


def main():
    first_name = input("Administrator's first name: ").strip()
    last_name = input("Administrator's last name: ").strip()
    email = input("New administrator's email: ").strip().lower()
    password = getpass.getpass("Password (8 to 128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if not first_name or not last_name or len(first_name) > 50 or len(last_name) > 50 or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise SystemExit("Enter a valid name and email.")
    if not 8 <= len(password) <= 128 or not password.strip() or password != confirmation:
        raise SystemExit("Check the password length and confirmation.")
    with app.app_context():
        try:
            user_id, _ = execute("INSERT INTO users (first_name, last_name, email, password_hash, role) VALUES (%s, %s, %s, %s, 'admin')",
                                 (first_name, last_name, email, generate_password_hash(password)))
            get_db().commit()
        except mysql.connector.IntegrityError:
            raise SystemExit("That email already exists. Use a new email for the administrator.")
    print("Administrator created. User ID:", user_id)
    print("Log in through the normal FitNut login page.")


if __name__ == "__main__":
    main()
