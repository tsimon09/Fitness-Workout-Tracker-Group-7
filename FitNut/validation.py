"""Input checks shared by the account and log routes."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from flask import request


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Choose Body > raw > JSON and send a JSON object")
    return data


def text(data, key, maximum, required=True):
    value = data.get(key)
    if not required and (value is None or value == ""):
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key.replace("_", " ").capitalize() + " is required")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(key.replace("_", " ").capitalize() + " is too long")
    return value


def number(data, key, positive=False, optional=False, maximum="99999999.99"):
    value = data.get(key)
    if optional and (value is None or value == ""):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError()
        value = Decimal(str(value))
        if not value.is_finite() or value > Decimal(maximum) or value < 0 or (positive and value == 0):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError(key.replace("_", " ").capitalize() + " must be a valid " +
                         ("positive number" if positive else "number of zero or more"))
    return value


def date_time(data, key, required=False):
    value = data.get(key)
    if not required and (value is None or value == ""):
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        if not isinstance(value, str):
            raise ValueError()
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is not None:
            date = date.astimezone(timezone.utc).replace(tzinfo=None)
        if date.year < 1970:
            raise ValueError()
        return date
    except (ValueError, TypeError):
        raise ValueError(key.replace("_", " ").capitalize() + " must be a valid date and time")
