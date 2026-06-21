from datetime import datetime
from database.db import get_db
from database.helpers import date_filter_clause


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    db = get_db()
    clause, params = date_filter_clause(date_from, date_to)
    try:
        cursor = db.execute(
            "SELECT amount, category, date, description FROM expenses"
            " WHERE user_id = ? " + clause
            + " ORDER BY date DESC LIMIT ?",
            (user_id,) + params + (limit,),
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
