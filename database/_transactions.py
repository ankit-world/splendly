from datetime import datetime
from database.db import get_db


def get_recent_transactions(user_id, limit=10):
    db = get_db()
    try:
        cursor = db.execute(
            "SELECT amount, category, date, description FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        transactions = []
        for row in rows:
            formatted_date = datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %d, %Y")
            transactions.append({
                "date": formatted_date,
                "description": row["description"],
                "category": row["category"],
                "amount": float(row["amount"])
            })
        return transactions
    finally:
        db.close()
