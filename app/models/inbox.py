"""Booking requests and contact-form messages."""
from ..db import execute, query


def add_booking(name, email, phone, service, date, notes):
    return execute("INSERT INTO bookings (name, email, phone, service, date, notes) VALUES (?, ?, ?, ?, ?, ?)",
                   (name, email, phone, service, date, notes))


def add_message(name, email, subject, message):
    return execute("INSERT INTO messages (name, email, subject, message) VALUES (?, ?, ?, ?)", (name, email, subject, message))


def bookings():
    return query("SELECT * FROM bookings ORDER BY id DESC")


def messages():
    return query("SELECT * FROM messages ORDER BY id DESC")


def unread_counts():
    b = query("SELECT COUNT(*) AS n FROM bookings WHERE is_read = 0", one=True)["n"]
    m = query("SELECT COUNT(*) AS n FROM messages WHERE is_read = 0", one=True)["n"]
    return {"bookings": b, "messages": m, "total": b + m}


def mark_all_read():
    execute("UPDATE bookings SET is_read = 1")
    execute("UPDATE messages SET is_read = 1")


def delete(kind, item_id):
    table = {"booking": "bookings", "message": "messages"}[kind]
    execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
