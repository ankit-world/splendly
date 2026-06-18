# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Spendly** is a personal expense-tracker web app built with Flask and SQLite. This is a practice/learning project built incrementally — many files are stubs that are filled in step by step.

## Development Setup

```bash
# Activate the virtual environment (Windows)
aenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the Flask development server (once app.py exists)
flask run
# or
python app.py
```

## Running Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run a single test by name
pytest tests/test_auth.py::test_login_success
```

## Architecture

This is a classic Flask server-rendered app with no frontend build step.

**Request flow:** Browser → `app.py` (Flask routes) → `database/db.py` (SQLite) → Jinja2 templates → HTML response

### Key files

- `app.py` — Flask application entry point and all route definitions (not yet created; students write this)
- `database/db.py` — SQLite helpers: `get_db()`, `init_db()`, `seed_db()` (stub; students implement)
- `templates/base.html` — shared layout: navbar, footer, Google Fonts (DM Sans + DM Serif Display), `static/css/style.css`, `static/js/main.js`
- `static/js/main.js` — client-side JS (stub; added as features are built)

### Database layer (`database/db.py`)

Three functions to implement:
- `get_db()` — returns a `sqlite3.connect()` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` — runs `CREATE TABLE IF NOT EXISTS` DDL for all tables
- `seed_db()` — inserts sample rows for local development

### Routes (referenced in templates)

| Flask endpoint | URL |
|---|---|
| `landing` | `/` |
| `login` | `/login` |
| `register` | `/register` |
| `terms` | `/terms` |
| `privacy` | `/privacy` |

### Template conventions

All pages `{% extends "base.html" %}` and fill `{% block title %}` and `{% block content %}`. The base template also exposes `{% block head %}` (extra `<head>` tags) and `{% block scripts %}` (page-level JS at end of body).

Auth forms post to `/login` and `/register` and expect the route to pass an `error` variable on failure (rendered as `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}`).
