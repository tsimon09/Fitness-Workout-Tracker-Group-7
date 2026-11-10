"""Registration, login, database sessions, and administrator permissions."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
import mysql.connector
from flask import Blueprint, current_app, g, make_response, redirect, request
from werkzeug.security import check_password_hash, generate_password_hash
from db import execute, fetch_all, fetch_one, get_db, to_json
from validation import payload, text

accounts = Blueprint("accounts", __name__)
COOKIE = "fitnut_session"
SESSION_HOURS = 8
DUMMY_HASH = generate_password_hash("unused-account-password")
USER_COLUMNS = "user_id, first_name, last_name, email, role, status, created_at, last_online"


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_token(token):
    return hashlib.sha256(("csrf:" + token).encode()).hexdigest()


def public_user(user):
    return to_json({key: user[key] for key in USER_COLUMNS.split(", ")})


def load_user():
    g.user = None
    g.session_token = None
    g.csrf_token = ""
    if request.endpoint == "static" or request.path == "/health":
        return
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return {"error": "This request must come from FitNut"}, 403
    token = request.cookies.get(COOKIE, "")
    if token and len(token) <= 128:
        user = fetch_one(
            "SELECT u.user_id, u.first_name, u.last_name, u.email, u.role, u.status, u.created_at, u.last_online, "
            "s.expires_at FROM sessions s JOIN users u ON u.user_id = s.user_id "
            "WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > UTC_TIMESTAMP(6)",
            (token_hash(token),),
        )
        if user and user["status"] == "active":
            g.user = user
            g.session_token = token
            g.csrf_token = csrf_token(token)
            execute("UPDATE users SET last_online = UTC_TIMESTAMP() WHERE user_id = %s", (user["user_id"],))
            get_db().commit()
    if (g.user and request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.path not in ("/login", "/register")):
        supplied = request.headers.get("X-CSRF-Token", "")
        if not re.fullmatch(r"[0-9a-f]{64}", supplied) or not secrets.compare_digest(supplied, g.csrf_token):
            return {"error": "Refresh the page or run Login in Postman again"}, 403


def login_required(html=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect("/login") if html else ({"error": "Please log in"}, 401)
            return function(*args, **kwargs)
        return wrapped
    return decorate


def admin_required(html=False):
    def decorate(function):
        @wraps(function)
        @login_required(html=html)
        def wrapped(*args, **kwargs):
            if g.user["role"] != "admin":
                return {"error": "Administrator access required"}, 403
            return function(*args, **kwargs)
        return wrapped
    return decorate


@accounts.post("/register")
def register():
    data = payload()
    first_name = text(data, "first_name", 50)
    last_name = text(data, "last_name", 50)
    email = text(data, "email", 254).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address")
    password = data.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128 or not password.strip():
        raise ValueError("Password must contain 8 to 128 characters")
    if password != data.get("password_confirmation"):
        raise ValueError("Passwords do not match")
    try:
        user_id, _ = execute("INSERT INTO users (first_name, last_name, email, password_hash) VALUES (%s, %s, %s, %s)",
                             (first_name, last_name, email, generate_password_hash(password)))
        get_db().commit()
    except mysql.connector.IntegrityError as error:
        get_db().rollback()
        if error.errno == 1062:
            return {"error": "Email already registered"}, 409
        raise
    return {"message": "Account created", "user_id": user_id}, 201


@accounts.post("/login")
def login():
    data = payload()
    email = text(data, "email", 254).lower()
    password = data.get("password")
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        raise ValueError("Enter your password")
    user = fetch_one("SELECT " + USER_COLUMNS + ", password_hash FROM users WHERE email = %s", (email,))
    correct = check_password_hash(user["password_hash"] if user else DUMMY_HASH, password)
    if not user or not correct:
        return {"error": "Email or password is incorrect"}, 401
    if user["status"] != "active":
        return {"error": "This account is suspended"}, 403
    old_token = request.cookies.get(COOKIE, "")
    if old_token:
        execute("UPDATE sessions SET revoked_at = UTC_TIMESTAMP(6) WHERE token_hash = %s AND revoked_at IS NULL",
                (token_hash(old_token),))
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=SESSION_HOURS)
    execute("INSERT INTO sessions (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user["user_id"], token_hash(token), expires))
    execute("UPDATE users SET last_online = UTC_TIMESTAMP() WHERE user_id = %s", (user["user_id"],))
    get_db().commit()
    user = fetch_one("SELECT " + USER_COLUMNS + " FROM users WHERE user_id = %s", (user["user_id"],))
    response = make_response({"message": "Logged in", "user": public_user(user),
                              "csrf_token": csrf_token(token), "expires_at": to_json(expires)})
    response.set_cookie(COOKIE, token, httponly=True, samesite="Lax", max_age=SESSION_HOURS * 3600,
                        secure=current_app.config["SESSION_COOKIE_SECURE"])
    return response


@accounts.get("/me")
@login_required()
def me():
    return {"user": public_user(g.user), "csrf_token": g.csrf_token,
            "expires_at": to_json(g.user["expires_at"])}


@accounts.post("/logout")
def logout():
    token = request.cookies.get(COOKIE, "")
    if token:
        execute("UPDATE sessions SET revoked_at = UTC_TIMESTAMP(6) WHERE token_hash = %s AND revoked_at IS NULL",
                (token_hash(token),))
        get_db().commit()
    response = make_response({"message": "Logged out"})
    response.delete_cookie(COOKIE, httponly=True, samesite="Lax", secure=current_app.config["SESSION_COOKIE_SECURE"])
    return response


@accounts.get("/admin/users")
@admin_required()
def list_users():
    return {"users": to_json(fetch_all("SELECT " + USER_COLUMNS + " FROM users ORDER BY user_id DESC LIMIT 200"))}


@accounts.patch("/admin/users/<int:user_id>")
@admin_required()
def update_user(user_id):
    data = payload()
    if not data or set(data) - {"role", "status"}:
        raise ValueError("Choose a role or account status")
    if user_id == g.user["user_id"]:
        raise ValueError("Use another administrator to change your own account")
    user = fetch_one("SELECT " + USER_COLUMNS + " FROM users WHERE user_id = %s", (user_id,))
    if not user:
        return {"error": "User not found"}, 404
    role, status = data.get("role", user["role"]), data.get("status", user["status"])
    if role not in ("user", "admin") or status not in ("active", "suspended"):
        raise ValueError("Choose a valid role and status")
    execute("UPDATE users SET role = %s, status = %s WHERE user_id = %s", (role, status, user_id))
    if role != user["role"] or status == "suspended":
        execute("UPDATE sessions SET revoked_at = UTC_TIMESTAMP(6) WHERE user_id = %s AND revoked_at IS NULL", (user_id,))
    get_db().commit()
    return {"message": "Account updated"}
