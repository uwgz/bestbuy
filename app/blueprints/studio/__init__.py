from flask import Blueprint

bp = Blueprint("studio", __name__)

from . import routes  # noqa: E402,F401
