from datetime import datetime

from database.db import get_user_by_id as _get_user_row
from database._transactions import get_recent_transactions
from database._stats import get_summary_stats
from database._categories import get_category_breakdown


def get_user_by_id(user_id):
    row = _get_user_row(user_id)
    if row is None:
        return None
    dt = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    parts = row["name"].split()
    initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else parts[0][:2].upper()
    return {
        "name":         row["name"],
        "email":        row["email"],
        "member_since": dt.strftime("%B %Y"),
        "initials":     initials,
    }


__all__ = [
    "get_user_by_id",
    "get_recent_transactions",
    "get_summary_stats",
    "get_category_breakdown",
]
