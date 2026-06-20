from database.db import get_db


def get_summary_stats(user_id):
    db = get_db()
    try:
        row = db.execute(
            "SELECT COUNT(*) as transaction_count, SUM(amount) as total_spent FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        transaction_count = row["transaction_count"] if row["transaction_count"] is not None else 0
        total_spent = float(row["total_spent"]) if row["total_spent"] is not None else 0.0

        top_row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        top_category = top_row["category"] if top_row is not None else "—"
    finally:
        db.close()

    return {
        "total_spent": total_spent,
        "transaction_count": int(transaction_count),
        "top_category": top_category,
    }
