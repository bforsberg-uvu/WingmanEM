"""
WingmanEM Flask Web App — root of the web application.

Run the Flask server and start the app when this script is executed:
  python web_app.py

Single functional route "/" takes the user to the main menu.
All existing menus and functionality are available via routes.
"""
import os
import sys
from datetime import date

# Ensure project root is on path so wingmanem and data files resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_user, logout_user

import wingmanem.app as app_module
import wingmanem.auth_users as auth_users_module

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB for uploads

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


class AuthUser(UserMixin):
    def __init__(self, pk: int, login_id: str, first_name: str, last_name: str):
        self.id = pk
        self.login_id = login_id
        self.first_name = first_name
        self.last_name = last_name


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id:
        return None
    try:
        pk = int(user_id)
    except ValueError:
        return None
    data = auth_users_module.get_user_by_id(pk)
    if not data:
        return None
    return AuthUser(
        data["id"],
        data["login_id"],
        data["first_name"],
        data["last_name"],
    )


_AUTH_EXEMPT_ENDPOINTS = frozenset({"login", "register", "static"})


def _safe_next_url(target: str | None) -> str | None:
    if not target or not isinstance(target, str):
        return None
    t = target.strip()
    if t.startswith("/") and not t.startswith("//"):
        return t
    return None


def init_data():
    """Init DB, migrate JSON into empty tables if needed, then load globals (DB-first, JSON mirrored)."""
    app_module._db_init()
    app_module._db_populate_from_json_files()
    app_module._load_direct_reports()
    app_module._load_management_tips()
    # Ensure goals JSON exists
    app_module._load_direct_report_goals()


@app.before_request
def _before_each_request():
    if not getattr(app_module, "_web_data_loaded", False):
        init_data()
        app_module._web_data_loaded = True

    if request.endpoint is None or request.endpoint in _AUTH_EXEMPT_ENDPOINTS:
        return None
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=request.full_path))


# ----- Auth (exempt from global login check) -----


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        uid = request.form.get("user_id", "").strip()
        pw = request.form.get("password", "")
        row = auth_users_module.verify_credentials(uid, pw)
        if row:
            login_user(
                AuthUser(row["id"], row["login_id"], row["first_name"], row["last_name"]),
                remember=False,
            )
            nxt = _safe_next_url(request.args.get("next") or request.form.get("next"))
            return redirect(nxt or url_for("index"))
        flash("Invalid user ID or password. Please try again.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        p1 = request.form.get("password", "")
        p2 = request.form.get("password_confirm", "")
        if p1 != p2:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        ok, err = auth_users_module.create_user(
            request.form.get("first_name", ""),
            request.form.get("last_name", ""),
            request.form.get("user_id", ""),
            p1,
        )
        if ok:
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        flash(err, "error")
    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("login"))


# ----- Main menu (single route that takes user to main menu) -----

@app.route("/")
def index():
    """Main menu — single functional route to the main menu."""
    tip = app_module._get_latest_management_tip()
    return render_template("main.html", tip=tip)


# ----- Project menu -----

@app.route("/project")
def project_menu():
    return render_template("project.html")


# ----- People menu -----

@app.route("/people")
def people_menu():
    return render_template("people.html")


# ----- Direct Reports -----

@app.route("/people/direct-reports")
def direct_reports_list():
    try:
        reports = app_module._db_load_direct_reports()
    except Exception:
        reports = []
    return render_template(
        "direct_reports.html",
        reports=reports,
        columns=app_module._LIST_DIRECT_REPORT_COLUMNS,
        show_generate=app_module.MISTRAL_AVAILABLE and bool(app_module._get_mistral_api_key()),
    )


@app.route("/people/direct-reports/add", methods=["GET", "POST"])
def direct_report_add():
    if request.method == "GET":
        return render_template("direct_report_add.html")
    # POST: build report from form
    report = {
        "id": app_module._next_direct_report_id(),
        "first_name": request.form.get("first_name", "").strip() or "Unknown",
        "last_name": request.form.get("last_name", "").strip() or "Unknown",
        "street_address_1": request.form.get("street_address_1", "").strip() or None,
        "street_address_2": request.form.get("street_address_2", "").strip() or None,
        "city": request.form.get("city", "").strip() or None,
        "state": request.form.get("state", "").strip() or None,
        "zipcode": request.form.get("zipcode", "").strip() or None,
        "country": request.form.get("country", "").strip() or None,
        "birthday": request.form.get("birthday", "").strip() or None,
        "hire_date": request.form.get("hire_date", "").strip() or None,
        "current_role": request.form.get("current_role", "").strip() or None,
        "role_start_date": request.form.get("role_start_date", "").strip() or None,
        "partner_name": request.form.get("partner_name", "").strip() or None,
    }
    report = app_module._normalize_direct_report(report)
    app_module.direct_reports.append(report)
    app_module._save_direct_reports()
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/edit/<int:item_id>", methods=["GET", "POST"])
def direct_report_edit(item_id):
    """Edit an existing direct report (same fields as add)."""
    report = next((r for r in app_module.direct_reports if r.get("id") == item_id), None)
    if report is None:
        return redirect(url_for("direct_reports_list"))
    if request.method == "GET":
        return render_template("direct_report_edit.html", report=report)
    updated = {
        "id": item_id,
        "first_name": request.form.get("first_name", "").strip() or "Unknown",
        "last_name": request.form.get("last_name", "").strip() or "Unknown",
        "street_address_1": request.form.get("street_address_1", "").strip() or None,
        "street_address_2": request.form.get("street_address_2", "").strip() or None,
        "city": request.form.get("city", "").strip() or None,
        "state": request.form.get("state", "").strip() or None,
        "zipcode": request.form.get("zipcode", "").strip() or None,
        "country": request.form.get("country", "").strip() or None,
        "birthday": request.form.get("birthday", "").strip() or None,
        "hire_date": request.form.get("hire_date", "").strip() or None,
        "current_role": request.form.get("current_role", "").strip() or None,
        "role_start_date": request.form.get("role_start_date", "").strip() or None,
        "partner_name": request.form.get("partner_name", "").strip() or None,
    }
    updated = app_module._normalize_direct_report(updated)
    idx = next(i for i, r in enumerate(app_module.direct_reports) if r.get("id") == item_id)
    app_module.direct_reports[idx] = updated
    app_module._save_direct_reports()
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/delete/<int:item_id>", methods=["GET", "POST"])
def direct_report_delete(item_id):
    """Confirm (GET) or perform (POST) deletion of a direct report."""
    report = next((r for r in app_module.direct_reports if r.get("id") == item_id), None)
    if report is None:
        return redirect(url_for("direct_reports_list"))
    if request.method == "GET":
        return render_template("direct_report_delete_confirm.html", report=report, item_id=item_id)
    index = next(
        (i for i, r in enumerate(app_module.direct_reports) if r.get("id") == item_id),
        None,
    )
    if index is not None:
        app_module._delete_goals_for_direct_report(item_id)
        app_module._db_purge_one_to_one_for_report(item_id)
        app_module._db_delete_comp_data_for_direct_report(item_id)
        app_module.direct_reports.pop(index)
        app_module._save_direct_reports()
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/purge", methods=["POST"])
def direct_reports_purge():
    app_module._delete_all_goals()
    app_module._delete_direct_report_comp_statements()
    app_module.direct_reports.clear()
    app_module._save_direct_reports()
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/generate", methods=["POST"])
def direct_reports_generate():
    if app_module.MISTRAL_AVAILABLE and app_module._get_mistral_api_key():
        num = request.form.get("num", "3")
        try:
            n = max(1, min(10, int(num)))
        except ValueError:
            n = 3
        from unittest.mock import patch
        with patch("builtins.input", side_effect=[str(n)]), patch(
            "wingmanem.app._clear_screen", lambda: None
        ):
            app_module._generate_direct_reports_with_ai()
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/generate_ratings", methods=["POST"])
def direct_reports_generate_ratings():
    """Generate direct report compensation statements from direct reports."""
    app_module._generate_direct_report_comp_statements()
    return redirect(url_for("direct_reports_list"))


# ----- Management tips -----

@app.route("/people/tips")
def tips_list():
    try:
        tips = app_module._db_load_management_tips()
    except Exception:
        tips = []
    return render_template("tips.html", tips=tips)


# ----- Milestone reminders -----

@app.route("/people/milestones")
def milestones():
    days = request.args.get("days", 30, type=int)
    days = max(1, min(365, days))
    try:
        db_reports = app_module._db_load_direct_reports()
        upcoming = app_module._compute_milestones_from_reports(db_reports, days)
    except Exception:
        upcoming = []
    return render_template(
        "milestones.html",
        days=days,
        upcoming=upcoming,
    )


# ----- 1:1 summaries -----

@app.route("/people/1to1")
def one_to_one_menu():
    reports = app_module.direct_reports
    report_summaries = []
    for r in reports:
        rid = r.get("id")
        if rid is None:
            continue
        summaries = app_module._db_get_one_to_one_summaries(rid)
        report_summaries.append((r, summaries))
    return render_template(
        "one_to_one_menu.html",
        reports=reports,
        report_summaries=report_summaries,
    )


@app.route("/people/1to1/view")
def one_to_one_view():
    report_id = request.args.get("report_id", type=int)
    if not report_id:
        return redirect(url_for("one_to_one_menu"))
    date_filter = request.args.get("date", "").strip()
    summaries = app_module._db_get_one_to_one_summaries(report_id)
    if date_filter:
        summaries = [s for s in summaries if s.get("date") == date_filter]
    report = next((r for r in app_module.direct_reports if r.get("id") == report_id), None)
    return render_template(
        "one_to_one_view.html",
        report_id=report_id,
        report=report,
        summaries=summaries,
    )


@app.route("/people/1to1/delete", methods=["GET", "POST"])
def one_to_one_delete():
    report_id = request.args.get("report_id", type=int) or (request.form.get("report_id", type=int))
    if not report_id:
        return redirect(url_for("one_to_one_menu"))
    summaries = app_module._db_get_one_to_one_summaries(report_id)
    report = next((r for r in app_module.direct_reports if r.get("id") == report_id), None)
    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        if date_str:
            app_module._db_delete_one_to_one_by_report_and_date(report_id, date_str)
        return redirect(url_for("one_to_one_view", report_id=report_id))
    return render_template(
        "one_to_one_delete.html",
        report_id=report_id,
        report=report,
        summaries=summaries,
    )


@app.route("/people/1to1/purge", methods=["GET", "POST"])
def one_to_one_purge():
    report_id = request.args.get("report_id", type=int) or (request.form.get("report_id", type=int))
    if not report_id:
        return redirect(url_for("one_to_one_menu"))
    report = next((r for r in app_module.direct_reports if r.get("id") == report_id), None)
    if request.method == "POST":
        app_module._db_purge_one_to_one_for_report(report_id)
        return redirect(url_for("one_to_one_menu"))
    return render_template("one_to_one_purge.html", report_id=report_id, report=report)


# ----- Upload 1:1 (simplified: form + handle file) -----

@app.route("/people/1to1/upload", methods=["GET", "POST"])
def one_to_one_upload():
    if request.method == "GET":
        upload_error = request.args.get("error")
        return render_template(
            "one_to_one_upload.html",
            reports=app_module.direct_reports,
            upload_error=upload_error,
        )
    report_id = request.form.get("report_id", type=int)
    if not report_id:
        return redirect(url_for("one_to_one_upload"))
    f = request.files.get("audio")
    if not f or not f.filename:
        return redirect(url_for("one_to_one_upload"))
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1]) as tmp:
        f.save(tmp.name)
        path = tmp.name
    try:
        if app_module.MISTRAL_AVAILABLE and app_module._get_mistral_api_key():
            try:
                from mistralai import Mistral
                import httpx
                client = Mistral(api_key=app_module._get_mistral_api_key())
                with open(path, "rb") as fp:
                    trans = client.audio.transcriptions.complete(
                        model="voxtral-mini-latest",
                        file={"file_name": f.filename, "content": fp.read()},
                    )
                transcript = (getattr(trans, "text", None) or "").strip()
                if transcript:
                    prompt = """Based on the following 1:1 meeting transcript, provide:
1) A brief summary (2–4 sentences).
2) A list of action items and to-dos (who does what, if clear).
3) Suggested follow-up topics for the next meeting.

Format the response clearly with headings (Summary, Action Items, Follow-ups). Use bullet points for lists."""
                    msg = client.chat.complete(
                        model="mistral-large-latest",
                        messages=[{"role": "user", "content": f"{prompt}\n\n--- Transcript ---\n{transcript}"}],
                    )
                    content = msg.choices[0].message.content or ""
                    if isinstance(content, list):
                        content = "".join(
                            p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p) for p in content
                        )
                    response_text = content.strip()
                    if response_text:
                        date_str = date.today().isoformat()
                        app_module._db_insert_one_to_one_summary(report_id, date_str, response_text)
                return redirect(url_for("one_to_one_view", report_id=report_id))
            except httpx.ReadError as e:
                return redirect(url_for("one_to_one_upload", error="ssl"))
            except (httpx.HTTPError, OSError) as e:
                return redirect(url_for("one_to_one_upload", error="connection"))
        return redirect(url_for("one_to_one_upload"))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return redirect(url_for("one_to_one_upload"))


# ----- Direct Report Goals (Chunk #5) -----

def _reports_with_goals():
    """Return list of direct reports that have at least one goal, with goal_count."""
    goals = app_module._load_direct_report_goals()
    by_report: dict[int, int] = {}
    for g in goals:
        rid = int(g.get("direct_report_id") or 0)
        if rid:
            by_report[rid] = by_report.get(rid, 0) + 1
    reports = []
    for r in app_module.direct_reports:
        rid = r.get("id")
        if rid and by_report.get(rid):
            r_copy = dict(r)
            r_copy["goal_count"] = by_report[rid]
            reports.append(r_copy)
    return reports


def _headers_for_display(headers) -> dict[str, str]:
    """Return headers safe for display (redacts sensitive values)."""
    redacted: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in {"cookie", "authorization"}:
            redacted[k] = "[redacted]"
        else:
            redacted[k] = v
    return redacted


def _raw_http_request_for_display(req, body_text: str = "") -> str:
    """Best-effort reconstructed raw HTTP request string.

    This is not a true wire capture; it is reconstructed from Flask/Werkzeug's parsed request.
    """
    proto = req.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
    full_path = req.full_path
    if full_path.endswith("?"):
        full_path = full_path[:-1]
    request_line = f"{req.method} {full_path} {proto}"
    hdrs = _headers_for_display(req.headers)
    header_lines = "\n".join([f"{k}: {v}" for k, v in hdrs.items()])
    if body_text:
        return f"{request_line}\n{header_lines}\n\n{body_text}"
    return f"{request_line}\n{header_lines}"


@app.route("/people/goals")
def goals_admin():
    """Administer Direct Report's Goals menu."""
    show_generate = app_module.MISTRAL_AVAILABLE and bool(app_module._get_mistral_api_key())
    return render_template("goals_admin.html", show_generate=show_generate)


@app.route("/people/goals/generate", methods=["GET", "POST"])
def goal_generate():
    """Generate goal data with Mistral AI (GET: form, POST: process)."""
    if not app_module.MISTRAL_AVAILABLE or not app_module._get_mistral_api_key():
        return redirect(url_for("goals_admin"))
    if request.method == "POST":
        try:
            num = max(1, min(20, int(request.form.get("num", "5"))))
        except ValueError:
            num = 5
        added = app_module._generate_goals_with_ai(num)
        return redirect(url_for("goals_admin", generated=added))
    return render_template("goal_generate.html")


@app.route("/items")
def comp_items():
    """Load direct report compensation rows from the database and render compensation statements."""
    try:
        items = app_module._db_load_direct_report_comp_data()
    except Exception:
        items = []
    if not items and app_module.direct_reports:
        app_module._generate_direct_report_comp_statements()
        try:
            items = app_module._db_load_direct_report_comp_data()
        except Exception:
            items = []
    # Build a simple lookup for rating labels
    rating_labels = {
        5: "Exceptional Contribution",
        4: "Exceed Expectations",
        3: "Meets Expectations",
        2: "Missed Expectations",
        1: "Needs improvement",
    }
    selected_report_id = request.args.get("report_id", type=int)
    selected_item = None
    if selected_report_id:
        for it in items:
            try:
                if int(it.get("direct_report_id") or 0) == selected_report_id:
                    selected_item = it
                    break
            except Exception:
                continue
    return render_template(
        "comp_items.html",
        items=items,
        rating_labels=rating_labels,
        selected_item=selected_item,
        selected_report_id=selected_report_id,
    )


@app.route("/people/goals/add", methods=["GET"])
def goal_add():
    """Display add goal form."""
    return render_template("goal_add.html", reports=app_module.direct_reports)


@app.route("/people/goals/add_goal", methods=["POST"])
def goal_add_post():
    """Process add goal form; save to JSON and DB; redirect to success page."""
    raw_body = request.get_data(cache=True, as_text=True)
    direct_report_id = request.form.get("direct_report_id", type=int)
    goal_title = request.form.get("goal_title", "").strip()
    goal_description = request.form.get("goal_description", "").strip()
    goal_completion_date = request.form.get("goal_completion_date", "").strip() or None
    if not direct_report_id:
        return redirect(url_for("goal_add"))
    goals = app_module._load_direct_report_goals()
    new_id = app_module._next_goal_id(goals)
    goal_dict = {
        "id": new_id,
        "direct_report_id": direct_report_id,
        "goal_title": goal_title[:50],
        "goal_description": goal_description[:100],
        "goal_completion_date": goal_completion_date[:10] if goal_completion_date else "",
    }
    goals.append(goal_dict)
    app_module._save_direct_report_goals(goals)
    # Store for success page
    from flask import session
    post_request = str(dict(request.form))
    post_raw_http = _raw_http_request_for_display(request, raw_body or "")
    session["last_added_goal"] = {
        "post_request": post_request,
        "post_raw_http": post_raw_http,
        "goal_dict": str(goal_dict),
        "json_contents": str(app_module._load_direct_report_goals()),
    }
    return redirect(url_for("goal_successfully_added"))


@app.route("/people/goals/goal_successfully_added")
def goal_successfully_added():
    """Display POST request, dictionary, JSON and DB contents after adding a goal."""
    from flask import session
    data = session.pop("last_added_goal", None)
    if not data:
        return redirect(url_for("goals_admin"))
    import json as json_mod
    json_contents = json_mod.dumps(app_module._load_direct_report_goals(), indent=2)
    db_rows = app_module._db_load_all_goals()
    report_names = {
        r.get("id"): f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "—"
        for r in app_module.direct_reports
        if r.get("id")
    }
    return render_template(
        "goal_successfully_added.html",
        post_request=data["post_request"],
        post_raw_http=data.get("post_raw_http") or data["post_request"],
        goal_dict=data["goal_dict"],
        json_filename=app_module.DIRECT_REPORT_GOALS_FILE,
        json_contents=json_contents,
        db_rows=db_rows,
        report_names=report_names,
    )


@app.route("/people/goals/view")
def goal_view():
    """View goals: table of direct reports that have goals."""
    reports_with_goals = _reports_with_goals()
    return render_template("goal_view.html", reports_with_goals=reports_with_goals)


@app.route("/people/goals/view_direct_report_goals")
def goal_view_report():
    """View goals for a specific direct report (GET with report_id)."""
    report_id = request.args.get("report_id", type=int)
    if not report_id:
        return redirect(url_for("goal_view"))
    goals = app_module._db_load_goals_for_report(report_id)
    report = next((r for r in app_module.direct_reports if r.get("id") == report_id), None)
    report_name = f"{report.get('first_name', '')} { report.get('last_name', '')} (ID {report_id})" if report else f"Report ID {report_id}"
    get_request = str(dict(request.args))
    get_raw_http = _raw_http_request_for_display(request, "")
    return render_template(
        "goal_view_report.html",
        report_id=report_id,
        report_name=report_name,
        goals=goals,
        get_request=get_request,
        get_raw_http=get_raw_http,
    )


@app.route("/people/goals/<int:goal_id>/edit", methods=["GET"])
def goal_edit(goal_id):
    """Display edit goal form."""
    goal = app_module._get_goal_by_id(goal_id)
    if not goal:
        return redirect(url_for("goal_view"))
    report_id = goal.get("direct_report_id")
    report = next((r for r in app_module.direct_reports if r.get("id") == report_id), None)
    report_name = f"{report.get('first_name', '')} {report.get('last_name', '')} (ID {report_id})" if report else f"Report ID {report_id}"
    return render_template(
        "goal_edit.html",
        goal=goal,
        goal_id=goal_id,
        report_id=report_id,
        report_name=report_name,
    )


@app.route("/people/goals/<int:goal_id>", methods=["PUT"])
def goal_update(goal_id):
    """Update a goal (PUT)."""
    from flask import session
    goal = app_module._get_goal_by_id(goal_id)
    if not goal:
        return "", 404
    report_id = goal.get("direct_report_id")
    goal_title = request.form.get("goal_title", "").strip()
    goal_description = request.form.get("goal_description", "").strip()
    goal_completion_date = request.form.get("goal_completion_date", "").strip() or None
    app_module._update_goal_by_id(goal_id, goal_title, goal_description, goal_completion_date)
    raw_body = request.get_data(cache=True, as_text=True)
    session["last_goal_request"] = {
        "request_type": "update",
        "raw_http": _raw_http_request_for_display(request, raw_body or ""),
        "report_id": report_id,
    }
    return redirect(url_for("goal_request_result"))


@app.route("/people/goals/<int:goal_id>", methods=["DELETE"])
def goal_delete(goal_id):
    """Delete a goal (DELETE)."""
    from flask import session
    goal = app_module._get_goal_by_id(goal_id)
    if not goal:
        return "", 404
    report_id = goal.get("direct_report_id")
    app_module._delete_goal_by_id(goal_id)
    session["last_goal_request"] = {
        "request_type": "delete",
        "raw_http": _raw_http_request_for_display(request, ""),
        "report_id": report_id,
    }
    return redirect(url_for("goal_request_result"))


@app.route("/people/goals/request_result")
def goal_request_result():
    """Show the UPDATE or DELETE request after edit/delete (from session)."""
    from flask import session
    data = session.pop("last_goal_request", None)
    if not data:
        return redirect(url_for("goals_admin"))
    return render_template(
        "goal_request_result.html",
        request_type=data["request_type"],
        raw_http=data["raw_http"],
        report_id=data["report_id"],
    )


@app.route("/people/goals/report/<int:report_id>/delete_all", methods=["POST"])
def goal_delete_all_for_report(report_id):
    """Delete all goals for a direct report."""
    app_module._delete_goals_for_direct_report(report_id)
    return redirect(url_for("goal_view"))


@app.route("/people/goals/delete_all", methods=["POST"])
def goal_delete_all():
    """Delete all goals for all direct reports."""
    app_module._delete_all_goals()
    return redirect(url_for("goal_view"))


@app.route("/people/goals/remove", methods=["GET", "POST"])
def goal_remove():
    """Remove goals: select direct report (GET) or process form (POST)."""
    if request.method == "POST":
        direct_report_id = request.form.get("direct_report_id", type=int)
        if direct_report_id:
            app_module._delete_goals_for_direct_report(direct_report_id)
        return redirect(url_for("goals_admin"))
    reports_with_goals = _reports_with_goals()
    return render_template("goal_remove.html", reports_with_goals=reports_with_goals)


# ----- Developer menu (optional) -----
# Register subpaths before /developer so routing stays unambiguous.


@app.route("/developer/schema")
def developer_schema():
    """SQLite DDL vs SQLAlchemy models (create_all, get_session)."""
    schema_pairs: list = []
    schema_error: str | None = None
    try:
        from wingmanem.developer_schema import build_schema_model_pairs

        schema_pairs = build_schema_model_pairs()
    except ImportError as e:
        schema_error = str(e)
    return render_template(
        "developer_schema.html",
        schema_pairs=schema_pairs,
        schema_error=schema_error,
    )


@app.route("/developer/comp-statements", endpoint="developer_comp_statements")
def developer_comp_statements():
    """Compensation statements: _db_load_direct_report_comp_data, DirectReportCompDataORM, Jinja."""
    return render_template("developer_comp_statements.html")


@app.route("/developer/direct-reports")
def developer_direct_reports():
    """DirectReportORM, _db_load_direct_reports, _db_replace_direct_reports_from_list."""
    return render_template("developer_direct_reports.html")


@app.route("/developer/system-users")
def developer_system_users():
    """Registered app users and password hashes (developer only)."""
    try:
        rows = auth_users_module.list_users_with_password_hashes()
    except Exception:
        rows = []
    return render_template("developer_system_users.html", users=rows)


@app.route("/developer/system-users/delete/<int:user_id>", methods=["GET", "POST"])
def developer_delete_application_user(user_id):
    """Remove an application user (not yourself)."""
    if user_id == current_user.id:
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("developer_system_users"))
    target = auth_users_module.get_user_by_id(user_id)
    if not target:
        flash("User not found.", "error")
        return redirect(url_for("developer_system_users"))
    if request.method == "GET":
        return render_template(
            "developer_delete_user_confirm.html",
            user_row=target,
            user_id=user_id,
        )
    ok, err = auth_users_module.delete_application_user(user_id)
    if ok:
        flash("User deleted.", "success")
    else:
        flash(err, "error")
    return redirect(url_for("developer_system_users"))


@app.route("/developer")
def developer_menu():
    """Developer hub: ORM models, SQLite schema, direct reports, comp statements."""
    return render_template("developer.html")


if __name__ == "__main__":
    init_data()
    app.run(host="0.0.0.0", port=5000, debug=True)
