"""
My account (/admin/account), for everyone who signs in:
    Password             change it (after signing in with the questions, no current password is asked)
    Security questions   five questions with answers only you know; answering all five correctly signs you in
                         when you can't remember the password (/admin/login/questions)
Answers are kept as hashes, like passwords, and don't care about capitals or spaces.
Five wrong tries in a row (password or answers) lock the account for 15 minutes.
"""
from flask import flash, g, redirect, render_template, request, session, url_for

from .admin import (FormError, audit, bp, home_for, locked_minutes, login_required, new_password, wrong_try)
from .extensions import db
from .models import SecurityQuestion, User, normal_answer

COUNT = 5
SUGGESTIONS = [
    "What is the name of the street you grew up on?",
    "What was the name of your first school?",
    "What is your mother's first name?",
    "What was the name of your first pet?",
    "In which town was your father born?",
    "What was your childhood nickname?",
    "What is the name of your best childhood friend?",
    "What was the first phone you owned?",
    "What was the first song you loved?",
    "What is your favourite meal?",
]


@bp.route("/account")
@login_required
def account():
    return render_template("admin/account.html", user=g.user, count=COUNT, suggestions=SUGGESTIONS,
                           reset=session.get("password_reset", False))


@bp.route("/account/password", methods=["POST"])
@login_required
def account_password():
    f = request.form
    try:
        if not session.get("password_reset") and not g.user.check_password(f.get("current", "")):
            raise FormError("Your current password isn't right.")
        g.user.set_password(new_password(f))
        session.pop("password_reset", None)
        audit("account.password", g.user.email)
        db.session.commit()
        flash("Password changed.", "success")
    except FormError as e:
        flash(str(e), "error")
    return redirect(url_for("admin.account"))


@bp.route("/account/questions", methods=["POST"])
@login_required
def account_questions():
    f = request.form
    try:
        if not session.get("password_reset") and not g.user.check_password(f.get("current", "")):
            raise FormError("Your current password isn't right. It's needed to change your questions.")
        pairs = []
        for i in range(1, COUNT + 1):
            question = " ".join((f.get(f"q{i}") or "").split())[:200]
            answer = f.get(f"a{i}") or ""
            if not question or not normal_answer(answer):
                raise FormError(f"Fill in question {i} and its answer.")
            if len(normal_answer(answer)) < 2:
                raise FormError(f"The answer to question {i} is too short.")
            pairs.append((question, answer))
        if len({q.lower() for q, _ in pairs}) < COUNT:
            raise FormError("Choose five different questions.")
        g.user.questions = []
        db.session.flush()
        for i, (question, answer) in enumerate(pairs):
            row = SecurityQuestion(position=i, question=question)
            row.set_answer(answer)
            g.user.questions.append(row)
        audit("account.questions", g.user.email)
        db.session.commit()
        flash("Security questions saved. You can now sign in with them if you forget your password.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin.account"))


@bp.route("/login/questions", methods=["GET", "POST"])
def login_questions():
    """Forgot the password: enter your email, then answer your five questions."""
    if g.user:
        return redirect(home_for(g.user))
    f, error, user = request.form, None, None
    if request.method == "POST":
        user = User.query.filter_by(email=f.get("email", "").strip().lower(), is_active=True).first()
        if not user or len(user.questions) < COUNT:
            user, error = None, "This email has no security questions. Ask the owner to reset your password."
        elif locked_minutes(user):
            wait = locked_minutes(user)
            user, error = None, f"Too many wrong tries. Wait {wait} minute{'s' if wait > 1 else ''}, then try again."
        elif f.get("step") == "answers":
            if all(q.check_answer(f.get(f"a{q.id}", "")) for q in user.questions):
                from .admin import _sign_in
                _sign_in(user, how="security questions")
                session["password_reset"] = True              # may choose a new password without the old one
                flash("You're signed in with your security questions. Choose a new password now.", "success")
                return redirect(url_for("admin.account", _anchor="password"))
            wrong_try(user, "login.questions_failed")
            if locked_minutes(user):
                user, error = None, "Too many wrong tries. Wait 15 minutes, then try again."
            else:
                error = "One or more answers are wrong. Check them and try again."
    return render_template("admin/login_questions.html", user=user, error=error, email=f.get("email", ""))
