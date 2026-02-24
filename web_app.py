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

from flask import Flask, redirect, render_template, request, url_for

import wingmanem.app as app_module

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB for uploads


def init_data():
    """Load data from files and DB at startup (same as CLI main())."""
    app_module._db_init()
    app_module._db_populate_from_json_files()
    app_module._load_direct_reports()
    app_module._load_management_tips()


@app.before_request
def ensure_data_loaded():
    if not getattr(app_module, "_web_data_loaded", False):
        init_data()
        app_module._web_data_loaded = True


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
    file_reports = app_module.direct_reports
    try:
        db_reports = app_module._db_load_direct_reports()
    except Exception:
        db_reports = []
    return render_template(
        "direct_reports.html",
        file_reports=file_reports,
        db_reports=db_reports,
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


@app.route("/people/direct-reports/delete", methods=["POST"])
def direct_report_delete():
    rid = request.form.get("id")
    if rid:
        try:
            target_id = int(rid)
            index = next(
                (i for i, r in enumerate(app_module.direct_reports) if r.get("id") == target_id),
                None,
            )
            if index is not None:
                app_module.direct_reports.pop(index)
                app_module._save_direct_reports()
        except ValueError:
            pass
    return redirect(url_for("direct_reports_list"))


@app.route("/people/direct-reports/purge", methods=["POST"])
def direct_reports_purge():
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


# ----- Management tips -----

@app.route("/people/tips")
def tips_list():
    file_tips = app_module.management_tips
    try:
        db_tips = app_module._db_load_management_tips()
    except Exception:
        db_tips = []
    return render_template("tips.html", file_tips=file_tips, db_tips=db_tips)


# ----- Milestone reminders -----

@app.route("/people/milestones")
def milestones():
    days = request.args.get("days", 30, type=int)
    days = max(1, min(365, days))
    file_reports = app_module.direct_reports
    file_upcoming = app_module._compute_milestones_from_reports(file_reports, days)
    try:
        db_reports = app_module._db_load_direct_reports()
        db_upcoming = app_module._compute_milestones_from_reports(db_reports, days)
    except Exception:
        db_reports = []
        db_upcoming = []
    return render_template(
        "milestones.html",
        days=days,
        file_upcoming=file_upcoming,
        db_upcoming=db_upcoming,
    )


# ----- 1:1 summaries -----

@app.route("/people/1to1")
def one_to_one_menu():
    return render_template("one_to_one_menu.html", reports=app_module.direct_reports)


@app.route("/people/1to1/view")
def one_to_one_view():
    report_id = request.args.get("report_id", type=int)
    if not report_id:
        return redirect(url_for("one_to_one_menu"))
    summaries = app_module._db_get_one_to_one_summaries(report_id)
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
        return render_template("one_to_one_upload.html", reports=app_module.direct_reports)
    report_id = request.form.get("report_id", type=int)
    if not report_id:
        return redirect(url_for("one_to_one_upload"))
    f = request.files.get("audio")
    if not f or not f.filename:
        return redirect(url_for("one_to_one_upload"))
    # Use app module's Mistral flow: save temp file, then call same logic
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.filename)[1]) as tmp:
        f.save(tmp.name)
        path = tmp.name
    try:
        if app_module.MISTRAL_AVAILABLE and app_module._get_mistral_api_key():
            from mistralai import Mistral
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
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return redirect(url_for("one_to_one_view", report_id=report_id))


# ----- Developer menu (optional) -----

@app.route("/developer")
def developer_menu():
    return render_template("developer.html")


if __name__ == "__main__":
    init_data()
    app.run(host="0.0.0.0", port=5000, debug=True)
