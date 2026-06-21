from datetime import date, datetime


def parse_date(val):
    try:
        return datetime.strptime(val, "%Y-%m-%d").date() if val else None
    except ValueError:
        return None


def months_ago(today, n):
    m, y = today.month - n, today.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def date_filter_clause(date_from, date_to):
    if date_from and date_to:
        return "AND date BETWEEN ? AND ?", (date_from, date_to)
    return "", ()
