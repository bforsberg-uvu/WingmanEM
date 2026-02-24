"""
Test that all enabled app functionality is reachable and runs without error.
Uses the real app module; run from project root: python -m pytest tests/test_app_enabled.py -v
or: python tests/test_app_enabled.py
"""
import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import patch

# Run from project root so wingmanem is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp dir for DB and JSON files so we don't touch real data
TEST_DIR = tempfile.mkdtemp(prefix="wingmanem_test_")


def test_import_app():
    """App module imports without error."""
    import wingmanem.app as app
    assert app.direct_reports is not None
    assert app.management_tips is not None


def test_db_init():
    """Database init runs and creates tables (or runs without DB if unavailable)."""
    with patch.dict(os.environ, {}, clear=False):
        with patch("wingmanem.app.DATABASE_PATH", os.path.join(TEST_DIR, "test.db")):
            import wingmanem.app as app
            app._db_init()
    # If _db_available is False we still pass (init handled it)
    assert True


def test_startup_missing_direct_reports_json():
    """Startup succeeds when direct_reports.json is missing; file is created with empty list."""
    td = tempfile.mkdtemp(prefix="wingmanem_dr_")
    dr_file = os.path.join(td, "direct_reports.json")
    assert not os.path.exists(dr_file)
    import wingmanem.app as app
    with patch("wingmanem.app.DIRECT_REPORTS_FILE", dr_file), patch(
        "wingmanem.app.DATABASE_PATH", os.path.join(td, "test.db")
    ):
        app._db_init()
        app._load_direct_reports()
    assert os.path.isfile(dr_file)
    with open(dr_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data == []
    assert app.direct_reports == []


def test_startup_missing_management_tips_json():
    """Startup succeeds when management_tips.json is missing; file is created (empty or with tip)."""
    td = tempfile.mkdtemp(prefix="wingmanem_tips_")
    tips_file = os.path.join(td, "management_tips.json")
    assert not os.path.exists(tips_file)
    import wingmanem.app as app
    with patch("wingmanem.app.MANAGEMENT_TIPS_FILE", tips_file), patch(
        "wingmanem.app.DATABASE_PATH", os.path.join(td, "test.db")
    ), patch("wingmanem.app._generate_management_tip_with_ai"):  # avoid Mistral call
        app._db_init()
        app._load_management_tips()
    assert os.path.isfile(tips_file)
    with open(tips_file, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert app.management_tips == data


def test_build_main_menu():
    """Main menu builds and contains expected options."""
    import wingmanem.app as app
    menu = app._build_main_menu()
    assert "WingmanEM" in menu
    assert "Project" in menu
    assert "People" in menu
    assert "Exit" in menu


def test_get_latest_management_tip():
    """Get latest tip returns a string (placeholder if none)."""
    import wingmanem.app as app
    tip = app._get_latest_management_tip()
    assert isinstance(tip, str)
    assert len(tip) > 0


def test_list_direct_reports_empty():
    """List direct reports runs (empty list is OK)."""
    import wingmanem.app as app
    app.direct_reports.clear()
    with patch("sys.stdout", new_callable=StringIO):
        app._list_direct_reports()
    assert True


def test_print_management_tips_by_date_empty():
    """Print management tips by date runs (empty is OK)."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("sys.stdout", new_callable=StringIO):
        app._print_management_tips_by_date()
    assert True


def test_compute_milestones_empty():
    """Compute milestones from empty reports returns empty list."""
    import wingmanem.app as app
    out = app._compute_milestones_from_reports([], 30)
    assert out == []


def test_prompt_direct_report_id_no_reports():
    """Prompt for direct report ID with no reports returns None."""
    import wingmanem.app as app
    app.direct_reports.clear()
    with patch("sys.stdout", new_callable=StringIO):
        result = app._prompt_direct_report_id()
    assert result is None


def test_view_one_to_one_responses_no_reports():
    """View 1:1 responses with no direct reports runs (exits early)."""
    import wingmanem.app as app
    app.direct_reports.clear()
    with patch("wingmanem.app._clear_screen"), patch("sys.stdout", new_callable=StringIO):
        app._view_one_to_one_responses()
    assert True


def test_delete_one_to_one_response_no_reports():
    """Delete 1:1 response with no reports runs (exits early)."""
    import wingmanem.app as app
    app.direct_reports.clear()
    with patch("wingmanem.app._clear_screen"), patch("sys.stdout", new_callable=StringIO):
        app._delete_one_to_one_response()
    assert True


def test_purge_one_to_one_responses_no_reports():
    """Purge 1:1 responses with no reports runs (exits early)."""
    import wingmanem.app as app
    app.direct_reports.clear()
    with patch("wingmanem.app._clear_screen"), patch("sys.stdout", new_callable=StringIO):
        app._purge_one_to_one_responses()
    assert True


def test_developer_menu_returns():
    """Developer menu runs and Back returns."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=1):
        app.run_developer_menu()
    assert True


def test_project_menu_back():
    """Project menu: select Back (4) returns."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=4):
        app.run_project_estimation_menu()
    assert True


def test_people_menu_back():
    """People menu: select Back (7) returns."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=7):
        app.run_people_coaching_menu()
    assert True


def test_direct_reports_menu_back():
    """Direct reports menu: select Back (6) returns."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=6):
        result = app.run_direct_reports_menu()
    assert result is True


def test_one_to_one_menu_back():
    """1:1 menu: select Back (5) returns."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=5):
        result = app.run_one_to_one_menu()
    assert result is True


def test_run_main_menu_exit():
    """Main menu: select Exit (3) returns False."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", return_value=3):
        result = app.run_main_menu()
    assert result is False


def test_run_main_menu_people_then_back_then_exit():
    """Main -> People (2) -> Back (7) from submenu -> back at main -> Exit (3)."""
    import wingmanem.app as app
    choices = [2, 7, 3]  # 1st: People, 2nd: Back (in People submenu), 3rd: Exit (on main)
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", side_effect=choices):
        r1 = app.run_main_menu()  # choice 2 -> People, then choice 7 -> Back; returns True
        r2 = app.run_main_menu()  # choice 3 -> Exit; returns False
    assert r1 is True
    assert r2 is False


def test_people_menu_view_management_tips():
    """People menu -> 6 (View management tips by date) -> 7 (Back)."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", side_effect=[6, 7]), patch("wingmanem.app._pause"):
        app.run_people_coaching_menu()
    assert True


def test_people_menu_direct_reports_then_list_then_back():
    """People -> 5 (Administer Direct Reports) -> 2 (List) -> 6 (Back) -> 7 (Back to main)."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", side_effect=[5, 2, 6, 7]), patch("wingmanem.app._pause"):
        app.run_people_coaching_menu()
    assert True


def test_people_menu_milestone_reminders_then_back():
    """People -> 4 (Milestone reminders) -> Enter to return from reminders -> 7 (Back)."""
    import wingmanem.app as app
    # _view_milestone_reminders has a loop: first shows 30 days, then asks "Enter days or Enter to return"
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", side_effect=[4, 7]), patch("builtins.input", return_value=""), patch("wingmanem.app._pause"):
        app.run_people_coaching_menu()
    assert True


def test_one_to_one_menu_view_then_back():
    """People -> 1 (1:1) -> 2 (View responses) -> 5 (Back) -> 7 (Back to main)."""
    import wingmanem.app as app
    with patch("wingmanem.app._clear_screen"), patch("wingmanem.app._prompt_choice", side_effect=[1, 2, 5, 7]), patch("wingmanem.app._pause"):
        app.run_people_coaching_menu()
    assert True


if __name__ == "__main__":
    # Run with: python tests/test_app_enabled.py
    import pytest
    pytest.main([__file__, "-v"])
