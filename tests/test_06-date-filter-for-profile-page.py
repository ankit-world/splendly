"""
tests/test_06-date-filter-for-profile-page.py

Tests for Step 6: Date Filter for the Profile Page.

All tests are based on the feature specification, not the implementation.
The spec defines:
  - GET /profile accepts optional `date_from` and `date_to` query params (YYYY-MM-DD)
  - All three data sections (stats, transactions, categories) respect the filter
  - date_from > date_to → flash "Start date must be before end date." + unfiltered fallback
  - Malformed date strings → silent unfiltered fallback (no crash)
  - Missing params → identical to Step-5 unfiltered behaviour
  - Template pre-fills date inputs with active filter values
  - Query helpers get_summary_stats, get_recent_transactions, get_category_breakdown
    each accept date_from/date_to kwargs
"""

import pytest
from datetime import date

from app import app as flask_app
from database.db import get_db, init_db, create_user
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app configured for testing with an isolated file-based SQLite DB
    placed in a temp directory so it does not touch the real spendly.db.
    A file-based DB (rather than :memory:) is needed because multiple
    get_db() calls inside query helpers each open their own connection, and
    :memory: gives every connection a separate, empty database.
    """
    db_file = str(tmp_path / "test_spendly.db")
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
        # Patch the DB_PATH used by get_db() via monkeypatching the module attr
    })
    # Monkeypatch the DB_PATH in database.db so all helpers use the temp DB
    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = db_file

    with flask_app.app_context():
        init_db()
        yield flask_app

    # Restore original path after test
    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app):
    """Creates a test user and returns (user_id, email, password)."""
    with app.app_context():
        user_id = create_user("Test User", "test@example.com", "testpass123")
    return user_id, "test@example.com", "testpass123"


@pytest.fixture
def auth_client(client, registered_user):
    """A test client already logged in as the registered user."""
    _, email, password = registered_user
    client.post("/login", data={"email": email, "password": password})
    return client


@pytest.fixture
def seeded_client(auth_client, registered_user, app):
    """
    Auth client whose user has a fixed set of expenses across two date ranges:

      RANGE A (2025-01-01 – 2025-01-31):
        - Food        200.00  2025-01-05
        - Transport    50.00  2025-01-10
        - Bills       300.00  2025-01-20
        Total A = 550.00  (3 transactions, top = Bills)

      RANGE B (2025-03-01 – 2025-03-31):
        - Health      150.00  2025-03-08
        - Shopping    400.00  2025-03-15
        Total B = 550.00  (2 transactions, top = Shopping)

    Grand total = 1100.00  (5 transactions)
    """
    user_id = registered_user[0]
    expenses = [
        (user_id, 200.0, "Food",      "2025-01-05", "Groceries Jan"),
        (user_id,  50.0, "Transport", "2025-01-10", "Metro Jan"),
        (user_id, 300.0, "Bills",     "2025-01-20", "Electricity Jan"),
        (user_id, 150.0, "Health",    "2025-03-08", "Pharmacy Mar"),
        (user_id, 400.0, "Shopping",  "2025-03-15", "Clothes Mar"),
    ]
    with app.app_context():
        db = get_db()
        db.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
        db.commit()
        db.close()
    return auth_client, user_id


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, (
            "Unauthenticated GET /profile must redirect (302)"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect must point to /login"
        )

    def test_unauthenticated_profile_with_date_params_redirects(self, client):
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        assert response.status_code == 302, (
            "Unauthenticated filtered request must also redirect"
        )
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# 2. Unfiltered profile — happy path
# ---------------------------------------------------------------------------

class TestUnfilteredProfile:
    def test_no_params_returns_200(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        assert response.status_code == 200, "Authenticated GET /profile must return 200"

    def test_no_params_shows_all_transactions(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # All five descriptions must appear
        assert "Groceries Jan"   in data, "All-time view must include Jan Food transaction"
        assert "Metro Jan"       in data, "All-time view must include Jan Transport transaction"
        assert "Electricity Jan" in data, "All-time view must include Jan Bills transaction"
        assert "Pharmacy Mar"    in data, "All-time view must include Mar Health transaction"
        assert "Clothes Mar"     in data, "All-time view must include Mar Shopping transaction"

    def test_no_params_total_spent_is_grand_total(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # Grand total is 1100.00
        assert "1100.00" in data, "Unfiltered total_spent must equal 1100.00"

    def test_no_params_transaction_count(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # 5 total transactions — the digit "5" will appear in the stats row
        assert "5" in data, "Unfiltered transaction_count must be 5"

    def test_rupee_symbol_always_present_unfiltered(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "₹" in data, "Rupee symbol must appear in unfiltered profile"


# ---------------------------------------------------------------------------
# 3. Date-filtered view — matching rows
# ---------------------------------------------------------------------------

class TestDateFilteredView:
    def test_filter_returns_200(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        assert response.status_code == 200, "Filtered GET /profile must return 200"

    def test_filter_shows_only_jan_transactions(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        assert "Groceries Jan"   in data, "Jan filter must include Jan Food"
        assert "Metro Jan"       in data, "Jan filter must include Jan Transport"
        assert "Electricity Jan" in data, "Jan filter must include Jan Bills"

    def test_filter_excludes_march_transactions(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        assert "Pharmacy Mar" not in data, "Jan filter must exclude Mar Health"
        assert "Clothes Mar"  not in data, "Jan filter must exclude Mar Shopping"

    def test_filter_stats_total_spent(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        # Range A total = 550.00
        assert "550.00" in data, "Filtered total_spent must equal 550.00 for Jan"

    def test_filter_stats_transaction_count(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        # 3 transactions in Jan
        assert "3" in data, "Filtered transaction_count must be 3 for Jan"

    def test_filter_stats_top_category_jan(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        # Bills = 300 is the highest in Jan
        assert "Bills" in data, "Top category for Jan must be Bills"

    def test_filter_category_breakdown_contains_only_jan_categories(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        # Jan has Food, Transport, Bills — Health and Shopping must not appear
        assert "Health"   not in data, "Category breakdown must not show Health for Jan filter"
        assert "Shopping" not in data, "Category breakdown must not show Shopping for Jan filter"

    def test_filter_march_shows_only_march_data(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-03-01&date_to=2025-03-31")
        data = response.data.decode("utf-8")
        assert "Pharmacy Mar" in data, "Mar filter must include Mar Health"
        assert "Clothes Mar"  in data, "Mar filter must include Mar Shopping"
        assert "Groceries Jan" not in data, "Mar filter must exclude Jan expenses"

    def test_filter_rupee_symbol_present_in_filtered_view(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        assert "₹" in data, "Rupee symbol must appear in filtered profile"


# ---------------------------------------------------------------------------
# 4. date_from > date_to — flash error + unfiltered fallback
# ---------------------------------------------------------------------------

class TestInvalidDateRange:
    def test_inverted_range_returns_200(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-03-31&date_to=2025-01-01")
        assert response.status_code == 200, "Inverted range must not crash — must return 200"

    def test_inverted_range_flashes_error_message(self, seeded_client):
        client, _ = seeded_client
        response = client.get(
            "/profile?date_from=2025-03-31&date_to=2025-01-01",
            follow_redirects=True,
        )
        data = response.data.decode("utf-8")
        assert "Start date must be before end date." in data, (
            "Inverted range must flash 'Start date must be before end date.'"
        )

    def test_inverted_range_falls_back_to_all_expenses(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-03-31&date_to=2025-01-01")
        data = response.data.decode("utf-8")
        # All five descriptions must be visible — unfiltered fallback
        assert "Groceries Jan"   in data, "Fallback must show Jan Food"
        assert "Pharmacy Mar"    in data, "Fallback must show Mar Health"
        assert "Clothes Mar"     in data, "Fallback must show Mar Shopping"

    def test_inverted_range_total_is_grand_total(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-03-31&date_to=2025-01-01")
        data = response.data.decode("utf-8")
        assert "1100.00" in data, "Fallback after inverted range must show grand total 1100.00"


# ---------------------------------------------------------------------------
# 5. Malformed date strings — silent fallback, no crash
# ---------------------------------------------------------------------------

class TestMalformedDateStrings:
    @pytest.mark.parametrize("date_from,date_to", [
        ("not-a-date", "also-bad"),
        ("2025/01/01", "2025/03/31"),
        ("01-01-2025", "31-03-2025"),
        ("",           "2025-03-31"),
        ("2025-01-01", ""),
        ("abcdefgh",   "12345678"),
        ("2025-13-01", "2025-03-31"),   # month 13 is invalid
        ("2025-01-32", "2025-03-31"),   # day 32 is invalid
    ])
    def test_malformed_dates_return_200(self, seeded_client, date_from, date_to):
        client, _ = seeded_client
        url = f"/profile?date_from={date_from}&date_to={date_to}"
        response = client.get(url)
        assert response.status_code == 200, (
            f"Malformed dates ({date_from!r}, {date_to!r}) must not crash the app"
        )

    def test_malformed_dates_fall_back_to_unfiltered(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=not-a-date&date_to=also-bad")
        data = response.data.decode("utf-8")
        # All five descriptions should be present — unfiltered fallback
        assert "Groceries Jan" in data, "Malformed date fallback must show all expenses"
        assert "Pharmacy Mar"  in data, "Malformed date fallback must show all expenses"


# ---------------------------------------------------------------------------
# 6. Valid range with zero matching expenses
# ---------------------------------------------------------------------------

class TestEmptyDateRange:
    def test_empty_range_returns_200(self, seeded_client):
        client, _ = seeded_client
        # 2025-02 has no expenses
        response = client.get("/profile?date_from=2025-02-01&date_to=2025-02-28")
        assert response.status_code == 200, "Empty date range must return 200"

    def test_empty_range_total_spent_is_zero(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-02-01&date_to=2025-02-28")
        data = response.data.decode("utf-8")
        assert "0.00" in data, "Empty date range must show ₹0.00 total_spent"

    def test_empty_range_no_transaction_rows(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-02-01&date_to=2025-02-28")
        data = response.data.decode("utf-8")
        # None of the seeded descriptions must appear
        assert "Groceries Jan"   not in data, "Empty range must show no Jan transactions"
        assert "Pharmacy Mar"    not in data, "Empty range must show no Mar transactions"

    def test_empty_range_rupee_symbol_still_present(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-02-01&date_to=2025-02-28")
        data = response.data.decode("utf-8")
        assert "₹" in data, "Rupee symbol must appear even when no expenses match the filter"


# ---------------------------------------------------------------------------
# 7. Date input fields pre-fill with active filter values
# ---------------------------------------------------------------------------

class TestDateInputPrefill:
    def test_active_date_from_prefills_input(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        assert 'value="2025-01-01"' in data, (
            "date_from input must be pre-filled with 2025-01-01"
        )

    def test_active_date_to_prefills_input(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        assert 'value="2025-01-31"' in data, (
            "date_to input must be pre-filled with 2025-01-31"
        )

    def test_no_params_inputs_have_empty_values(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # The filter form's date inputs should have empty value attributes
        assert 'name="date_from"' in data, "date_from input must be present"
        assert 'name="date_to"'   in data, "date_to input must be present"

    def test_active_filter_label_displayed(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile?date_from=2025-01-01&date_to=2025-01-31")
        data = response.data.decode("utf-8")
        # The template renders a "Showing:" label when both params are active
        assert "2025-01-01" in data, "Active date_from must appear in the filter label"
        assert "2025-01-31" in data, "Active date_to must appear in the filter label"

    def test_all_time_url_has_no_filter_label(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # "Showing:" label is only rendered when both date params are active
        assert "filter-active-label" not in data or "Showing:" not in data, (
            "All-time view must not show an active filter label"
        )


# ---------------------------------------------------------------------------
# 8. Direct unit tests for query helpers — date_from/date_to kwargs
# ---------------------------------------------------------------------------

class TestGetSummaryStats:
    def test_no_filter_returns_all_expenses(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats = get_summary_stats(user_id)
        assert stats["transaction_count"] == 5, (
            "Unfiltered get_summary_stats must count all 5 transactions"
        )
        assert stats["total_spent"] == pytest.approx(1100.0), (
            "Unfiltered get_summary_stats total_spent must be 1100.00"
        )

    def test_date_filter_returns_jan_stats(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats = get_summary_stats(user_id, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["transaction_count"] == 3, (
            "Filtered get_summary_stats must count 3 Jan transactions"
        )
        assert stats["total_spent"] == pytest.approx(550.0), (
            "Filtered get_summary_stats total_spent must be 550.00 for Jan"
        )

    def test_date_filter_top_category_jan(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats = get_summary_stats(user_id, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["top_category"] == "Bills", (
            "Top category for Jan must be Bills (highest amount 300.00)"
        )

    def test_date_filter_top_category_march(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats = get_summary_stats(user_id, date_from="2025-03-01", date_to="2025-03-31")
        assert stats["top_category"] == "Shopping", (
            "Top category for March must be Shopping (highest amount 400.00)"
        )

    def test_empty_range_returns_zero_stats(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats = get_summary_stats(user_id, date_from="2025-02-01", date_to="2025-02-28")
        assert stats["transaction_count"] == 0, "Empty range must have 0 transactions"
        assert stats["total_spent"] == pytest.approx(0.0), "Empty range total_spent must be 0.0"

    def test_none_filters_match_unfiltered(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            stats_none    = get_summary_stats(user_id, date_from=None, date_to=None)
            stats_noargs  = get_summary_stats(user_id)
        assert stats_none["total_spent"] == stats_noargs["total_spent"], (
            "Passing date_from=None, date_to=None must behave identically to no kwargs"
        )
        assert stats_none["transaction_count"] == stats_noargs["transaction_count"]


class TestGetRecentTransactions:
    def test_no_filter_returns_all_transactions(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(user_id)
        assert len(txns) == 5, (
            "Unfiltered get_recent_transactions must return all 5 transactions"
        )

    def test_date_filter_returns_jan_transactions_only(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        assert len(txns) == 3, (
            "Filtered get_recent_transactions must return 3 Jan transactions"
        )
        descriptions = [t["description"] for t in txns]
        assert "Groceries Jan"   in descriptions
        assert "Metro Jan"       in descriptions
        assert "Electricity Jan" in descriptions

    def test_date_filter_excludes_non_matching_transactions(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        descriptions = [t["description"] for t in txns]
        assert "Pharmacy Mar" not in descriptions, (
            "Jan filter must exclude Mar Health transaction"
        )
        assert "Clothes Mar" not in descriptions, (
            "Jan filter must exclude Mar Shopping transaction"
        )

    def test_transactions_ordered_newest_first(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        # Jan 20 > Jan 10 > Jan 05; formatted as "Jan 20, 2025" etc.
        assert "Jan 20, 2025" == txns[0]["date"], (
            "Transactions must be ordered newest first within the filtered range"
        )

    def test_empty_range_returns_empty_list(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(
                user_id, date_from="2025-02-01", date_to="2025-02-28"
            )
        assert txns == [], "Empty date range must return empty transactions list"

    def test_none_filters_match_unfiltered(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns_none   = get_recent_transactions(user_id, date_from=None, date_to=None)
            txns_noargs = get_recent_transactions(user_id)
        assert len(txns_none) == len(txns_noargs), (
            "date_from=None, date_to=None must behave identically to no kwargs"
        )

    def test_transaction_dict_keys_present(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            txns = get_recent_transactions(user_id)
        assert len(txns) > 0
        for txn in txns:
            assert "date"        in txn, "Each transaction must have 'date' key"
            assert "description" in txn, "Each transaction must have 'description' key"
            assert "category"    in txn, "Each transaction must have 'category' key"
            assert "amount"      in txn, "Each transaction must have 'amount' key"


class TestGetCategoryBreakdown:
    def test_no_filter_returns_all_categories(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(user_id)
        category_names = [c["name"] for c in cats]
        assert "Food"      in category_names, "Unfiltered breakdown must include Food"
        assert "Transport" in category_names, "Unfiltered breakdown must include Transport"
        assert "Bills"     in category_names, "Unfiltered breakdown must include Bills"
        assert "Health"    in category_names, "Unfiltered breakdown must include Health"
        assert "Shopping"  in category_names, "Unfiltered breakdown must include Shopping"

    def test_date_filter_jan_categories(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        category_names = [c["name"] for c in cats]
        assert "Food"      in category_names, "Jan breakdown must include Food"
        assert "Transport" in category_names, "Jan breakdown must include Transport"
        assert "Bills"     in category_names, "Jan breakdown must include Bills"

    def test_date_filter_jan_excludes_march_categories(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        category_names = [c["name"] for c in cats]
        assert "Health"   not in category_names, "Jan breakdown must not include Health"
        assert "Shopping" not in category_names, "Jan breakdown must not include Shopping"

    def test_percentages_sum_to_100(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(user_id)
        total_pct = sum(c["pct"] for c in cats)
        assert total_pct == 100, (
            f"Category percentages must sum to 100, got {total_pct}"
        )

    def test_filtered_percentages_sum_to_100(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        total_pct = sum(c["pct"] for c in cats)
        assert total_pct == 100, (
            f"Filtered category percentages must sum to 100, got {total_pct}"
        )

    def test_empty_range_returns_empty_list(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(
                user_id, date_from="2025-02-01", date_to="2025-02-28"
            )
        assert cats == [], "Empty date range must return empty category list"

    def test_category_amounts_correct_for_jan(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(
                user_id, date_from="2025-01-01", date_to="2025-01-31"
            )
        amounts = {c["name"]: c["amount"] for c in cats}
        assert amounts["Bills"]     == pytest.approx(300.0), "Bills Jan amount must be 300.00"
        assert amounts["Food"]      == pytest.approx(200.0), "Food Jan amount must be 200.00"
        assert amounts["Transport"] == pytest.approx(50.0),  "Transport Jan amount must be 50.00"

    def test_none_filters_match_unfiltered(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats_none   = get_category_breakdown(user_id, date_from=None, date_to=None)
            cats_noargs = get_category_breakdown(user_id)
        assert len(cats_none) == len(cats_noargs), (
            "date_from=None, date_to=None must behave identically to no kwargs"
        )

    def test_category_dicts_have_required_keys(self, app, seeded_client):
        _, user_id = seeded_client
        with app.app_context():
            cats = get_category_breakdown(user_id)
        for cat in cats:
            assert "name"   in cat, "Each category must have 'name' key"
            assert "amount" in cat, "Each category must have 'amount' key"
            assert "pct"    in cat, "Each category must have 'pct' key"


# ---------------------------------------------------------------------------
# 9. Template rendering landmarks
# ---------------------------------------------------------------------------

class TestTemplateRendering:
    def test_profile_renders_filter_bar(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "filter-bar"    in data, "Profile page must render the filter bar"
        assert "filter-input"  in data, "Profile page must render date filter inputs"

    def test_profile_renders_stats_row(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "stats-row"   in data or "Total Spent" in data, (
            "Profile page must render the stats row"
        )

    def test_profile_renders_transaction_table(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "txn-table" in data or "Transaction History" in data, (
            "Profile page must render the transaction table"
        )

    def test_profile_renders_category_breakdown(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "breakdown-list" in data or "Spending by Category" in data, (
            "Profile page must render the category breakdown section"
        )

    def test_profile_renders_preset_buttons(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "This Month"    in data, "Filter bar must contain 'This Month' preset"
        assert "Last 3 Months" in data, "Filter bar must contain 'Last 3 Months' preset"
        assert "Last 6 Months" in data, "Filter bar must contain 'Last 6 Months' preset"
        assert "All Time"      in data, "Filter bar must contain 'All Time' preset"

    def test_profile_extends_base_html(self, seeded_client):
        client, _ = seeded_client
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # base.html typically provides a <html> tag and a nav
        assert "<html" in data, "Profile page must extend base.html (full HTML doc expected)"
