from datetime import datetime

from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

SEED_USER_ID = 1  # demo@spendly.com, seeded by seed_db() on app startup


# ------------------------------------------------------------------ #
# get_user_by_id                                                      #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid():
    user = get_user_by_id(SEED_USER_ID)
    assert user is not None
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    datetime.strptime(user["member_since"], "%B %Y")  # must parse without error


def test_get_user_by_id_nonexistent():
    assert get_user_by_id(99999) is None


# ------------------------------------------------------------------ #
# get_summary_stats                                                   #
# ------------------------------------------------------------------ #

def test_get_summary_stats_with_expenses():
    stats = get_summary_stats(SEED_USER_ID)
    assert stats["total_spent"] == 3550.0
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(empty_user_id):
    stats = get_summary_stats(empty_user_id)
    assert stats["total_spent"] == 0.0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


# ------------------------------------------------------------------ #
# get_recent_transactions                                             #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_with_expenses():
    txns = get_recent_transactions(SEED_USER_ID)
    assert len(txns) == 8
    for txn in txns:
        assert "date" in txn
        assert "description" in txn
        assert "category" in txn
        assert "amount" in txn
    dates = [datetime.strptime(t["date"], "%b %d, %Y") for t in txns]
    assert dates == sorted(dates, reverse=True)


def test_get_recent_transactions_no_expenses(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


# ------------------------------------------------------------------ #
# get_category_breakdown                                              #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_with_expenses():
    cats = get_category_breakdown(SEED_USER_ID)
    assert len(cats) == 7
    assert sum(c["pct"] for c in cats) == 100
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)


def test_get_category_breakdown_no_expenses(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


# ------------------------------------------------------------------ #
# GET /profile route                                                  #
# ------------------------------------------------------------------ #

def test_profile_unauthenticated(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_profile_authenticated(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
    assert "3550.00" in body
    assert "Bills" in body
    assert "Jun 17, 2026" in body


def test_profile_category_breakdown_count(client):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.get("/profile")
    body = response.data.decode("utf-8")
    for cat in ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"):
        assert cat in body
