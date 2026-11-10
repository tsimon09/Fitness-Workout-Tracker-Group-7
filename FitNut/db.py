"""Small helpers for MySQL. Every query supplies its values separately."""
import os
from datetime import datetime
from decimal import Decimal
import mysql.connector
from flask import g


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]),
            user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"], time_zone="+00:00", connection_timeout=5,
        )
    return g.db


def fetch_all(sql, values=()):
    cursor = get_db().cursor(dictionary=True)
    try:
        cursor.execute(sql, values)
        return cursor.fetchall()
    finally:
        cursor.close()


def fetch_one(sql, values=()):
    rows = fetch_all(sql, values)
    return rows[0] if rows else None


def execute(sql, values=()):
    cursor = get_db().cursor()
    try:
        cursor.execute(sql, values)
        return cursor.lastrowid, cursor.rowcount
    finally:
        cursor.close()


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def to_json(value):
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + "Z"
    if isinstance(value, Decimal):
        return float(value)
    return value
