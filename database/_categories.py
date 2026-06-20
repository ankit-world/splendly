from database.db import get_db


def get_category_breakdown(user_id):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,)
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
