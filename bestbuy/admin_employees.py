"""
Employees (/admin/employees), for the owner: the people who can sign in, and what each may do.

    + Add employee     name, email, role (owner, manager or employee) and a first password to give them
    Edit               name, email, role
    New password       when someone forgot theirs (also ends a 15-minute lock)
    Remove access      they can't sign in any more; their sales and history stay. "Give access back" undoes it.
There is always at least one owner who can sign in, and you can't change your own role or remove yourself.
"""
from flask import flash, g, redirect, render_template, request, url_for

from .admin import FormError, audit, bp, login_required, new_password, valid_email
from .extensions import db
from .models import ROLES, User


@bp.route("/employees")
@login_required
def employees():
    people = User.query.order_by(User.is_active.desc(), User.name).all()
    return render_template("admin/employees.html", people=people, roles=ROLES)


def _back():
    return redirect(url_for("admin.employees"))


def _person(user_id):
    person = db.session.get(User, user_id)
    if not person:
        raise FormError("That person was not found.")
    return person


def _details(f, person=None):
    name = " ".join((f.get("name") or "").split())[:80]
    email = (f.get("email") or "").strip().lower()
    role = f.get("role", "")
    if not name:
        raise FormError("Fill in the name.")
    if not valid_email(email):
        raise FormError("Enter a valid email address.")
    if role not in ROLES:
        raise FormError("Choose a role.")
    taken = User.query.filter(User.email == email, User.id != (person.id if person else 0)).first()
    if taken:
        raise FormError(f"{email} already has an account ({taken.name}).")
    return name, email, role


def _owners_left(without):
    return User.query.filter(User.role == "owner", User.is_active.is_(True), User.id != without.id).count()


@bp.route("/employees/add", methods=["POST"])
@login_required
def employee_add():
    try:
        name, email, role = _details(request.form)
        person = User(name=name, email=email, role=role)
        person.set_password(new_password(request.form))
        db.session.add(person)
        db.session.flush()
        audit("employee.add", f"{email} as {role}")
        db.session.commit()
        flash(f"{name} can now sign in with {email} as {ROLES[role][0].lower()}. Give them their password; "
              "they can change it in My account.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back()


@bp.route("/employees/<int:user_id>/edit", methods=["POST"])
@login_required
def employee_edit(user_id):
    try:
        person = _person(user_id)
        name, email, role = _details(request.form, person)
        if role != person.role:
            if person.id == g.user.id:
                raise FormError("You can't change your own role. Another owner can.")
            if person.role == "owner" and person.is_active and not _owners_left(person):
                raise FormError("There must always be an owner.")
        person.name, person.email, person.role = name, email, role
        audit("employee.edit", f"{email} as {role}")
        db.session.commit()
        flash(f"{name} saved.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back()


@bp.route("/employees/<int:user_id>/password", methods=["POST"])
@login_required
def employee_password(user_id):
    try:
        person = _person(user_id)
        person.set_password(new_password(request.form))
        person.failed_logins, person.locked_until = 0, None
        audit("employee.password", person.email)
        db.session.commit()
        flash(f"New password set for {person.name}. Give it to them; they can change it in My account.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back()


@bp.route("/employees/<int:user_id>/access", methods=["POST"])
@login_required
def employee_access(user_id):
    try:
        person = _person(user_id)
        if person.id == g.user.id:
            raise FormError("You can't remove your own access.")
        if person.is_active and person.role == "owner" and not _owners_left(person):
            raise FormError("There must always be an owner.")
        person.is_active = not person.is_active
        audit("employee.access" if person.is_active else "employee.removed", person.email)
        db.session.commit()
        flash(f"{person.name} can sign in again." if person.is_active else f"{person.name} can't sign in any more.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back()
