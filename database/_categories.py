from database.db import get_db
from database.helpers import date_filter_clause


def get_category_breakdown(user_id, date_from=None, date_to=None):
    db = get_db()
    clause, params = date_filter_clause(date_from, date_to)
    try:
        rows = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses"
            " WHERE user_id = ? " + clause
            + " GROUP BY category ORDER BY total DESC",
            (user_id,) + params,
        ).fetchall()

        if not rows:
            return []

        grand_total = sum(row["total"] for row in rows)

        categories = [
            {"name": row["category"], "amount": float(row["total"]), "pct": round(row["total"] / grand_total * 100)}
            for row in rows
        ]

        pct_sum = sum(c["pct"] for c in categories)
        if pct_sum != 100:
            categories[0]["pct"] += 100 - pct_sum

        return categories
    finally:
        db.close()
