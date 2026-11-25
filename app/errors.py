"""
Error pages for every kind of error (404, 403, 500 …).
Each error gets a friendly title, an explanation and helpful next steps.
"""
import logging

from flask import render_template, request
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)

# code: (title, message, show_search)
PAGES = {
    400: ("Something went wrong.", "We couldn't understand that request. Go back, refresh the page and try again.", False),
    401: ("Please sign in.", "You need to sign in to see this page.", False),
    403: ("This page is private.", "You don't have access to this page.", False),
    404: ("Page not found.", "The page you're looking for doesn't exist or has moved. Try searching the shop instead.", True),
    405: ("That didn't work.", "This page can't be opened that way. Go back and use the buttons on the page.", False),
    408: ("That took too long.", "The page took too long to respond. Please try again.", False),
    410: ("This page is gone.", "This page has been removed for good.", True),
    413: ("That upload is too big.", "Try fewer photos at once, or smaller photos (under 25 MB in total).", False),
    415: ("We can't use that file.", "Please upload a JPG, PNG, WebP or AVIF photo.", False),
    429: ("Slow down a little.", "Too many attempts in a short time. Please wait a few minutes and try again.", False),
    500: ("Something broke on our side.", "We're sorry — please try again in a moment. If it keeps happening, call or message us.", False),
    502: ("We're having trouble.", "Our server isn't responding right now. Please try again in a moment.", False),
    503: ("We'll be right back.", "The site is being updated. Please try again in a few minutes.", False),
}


def render_error(code, description=None):
    title, message, show_search = PAGES.get(code, PAGES[500] if code >= 500 else PAGES[400])
    # use the specific reason when the code gave one (e.g. "Your session expired")
    if description and code in (400, 403, 413, 415, 429) and not description.startswith(("The browser", "You don't have the permission", "The data value")):
        message = description
    try:
        html = render_template("errors/error.html", code=code, title=title, message=message,
                               show_search=show_search, in_admin=request.path.startswith("/altar"))
    except Exception:  # the error page itself must never fail (e.g. database down)
        log.exception("Error page could not render")
        html = (f"<!doctype html><meta charset=utf-8><title>{code}</title>"
                f"<body style='font-family:system-ui;text-align:center;padding:15vh 20px'>"
                f"<h1 style='font-size:64px;margin:0'>{code}</h1><p>{title}</p><a href='/'>Go to the home page</a>")
    resp = (html, code)
    return resp


def init_app(app):
    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.code is None or e.code < 400:   # redirects etc. are not errors
            return e
        return render_error(e.code, e.description)

    @app.errorhandler(Exception)
    def unexpected(e):
        if isinstance(e, HTTPException):
            return http_error(e)
        if app.config.get("DEBUG") or app.config.get("TESTING") and app.config.get("PROPAGATE_EXCEPTIONS"):
            raise e  # show the real error while developing
        log.exception("Unhandled error on %s", request.path)
        return render_error(500)

    @app.after_request
    def no_cache_errors(resp):
        if resp.status_code >= 400:
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["X-Robots-Tag"] = "noindex"
        return resp
