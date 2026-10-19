"""Run FitNut with: python app.py."""
import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv(Path(__file__).with_name(".env.local"))

from accounts import accounts, load_user, login_required, admin_required
from db import close_db, fetch_all, fetch_one, to_json
from logs import logs, LOG_TYPES
from log_data import count_items, read_items, meal_choices
from profiles import profiles

app = Flask(__name__)
trusted_hosts = [host.strip() for host in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
if os.getenv("RAILWAY_PUBLIC_DOMAIN"):
    trusted_hosts.extend([os.environ["RAILWAY_PUBLIC_DOMAIN"], "healthcheck.railway.app"])
app.config.update(MAX_CONTENT_LENGTH=65536, TRUSTED_HOSTS=trusted_hosts,
                  SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true")
# The hosting server forwards HTTPS traffic to Flask over an internal connection.
if os.getenv("TRUST_PROXY", "false").lower() == "true":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)
app.register_blueprint(accounts)
app.register_blueprint(logs)
app.register_blueprint(profiles)
app.before_request(load_user)
app.teardown_appcontext(close_db)


@app.after_request
def response_headers(response):
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.errorhandler(ValueError)
def invalid_input(error):
    return {"error": str(error)}, 400


@app.errorhandler(mysql.connector.IntegrityError)
def invalid_database_value(error):
    return {"error": "Check the values you entered"}, 400


@app.errorhandler(mysql.connector.Error)
def database_unavailable(error):
    app.logger.warning("Database operation failed, error code %s", error.errno)
    return {"error": "The database is unavailable. Please try again shortly."}, 503


@app.get("/health")
def health():
    return {"message": "FitNut is running"}


@app.get("/")
def home():
    return redirect("/dashboard") if g.user else render_template("home.html")


@app.get("/register")
def register_page():
    return redirect("/dashboard") if g.user else render_template("account.html", mode="register")


@app.get("/login")
def login_page():
    return redirect("/dashboard") if g.user else render_template("account.html", mode="login")


@app.get("/dashboard")
@login_required(html=True)
def dashboard():
    counts = {}
    for kind, settings in LOG_TYPES.items():
        counts[kind] = count_items(kind)
    return render_template("dashboard.html", counts=counts)


@app.get("/food")
@app.get("/activity")
@app.get("/sleep")
@login_required(html=True)
def log_page():
    kind = request.path[1:]
    settings = LOG_TYPES[kind]
    return render_template("logs.html", kind=kind, settings=settings, records=to_json(read_items(kind)),
                           meals=to_json(meal_choices()) if kind == 'food' else [],
                           profile=fetch_one('SELECT * FROM user_profiles WHERE user_id=%s', (g.user['user_id'],)),
                           units=fetch_all('SELECT unit_name FROM units_of_measure ORDER BY unit_name'),
                           activities=fetch_all('SELECT activity_name FROM activity_types ORDER BY activity_name'))


@app.get("/admin")
@admin_required(html=True)
def admin_page():
    users = fetch_all("SELECT user_id, first_name, last_name, email, role, status, created_at, last_online "
                      "FROM users ORDER BY user_id DESC LIMIT 200")
    return render_template("admin.html", users=to_json(users))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
