from database.db import get_db
from database.helpers import date_filter_clause


def get_summary_stats(user_id, date_from=None, date_to=None):
    db = get_db()
    clause, params = date_filter_clause(date_from, date_to)
    try:
        row = db.execute(
            "SELECT COUNT(*) as transaction_count, SUM(amount) as total_spent"
            " FROM expenses WHERE user_id = ? " + clause,
            (user_id,) + params,
        ).fetchone()
        top_row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ? " + clause
            + " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,) + params,
        ).fetchone()

        transaction_count = row["transaction_count"] if row["transaction_count"] is not None else 0
        total_spent = float(row["total_spent"]) if row["total_spent"] is not None else 0.0
        top_category = top_row["category"] if top_row is not None else "—"
    finally:
        db.close()

    return {
        "total_spent": total_spent,
        "transaction_count": int(transaction_count),
        "top_category": top_category,
    }
