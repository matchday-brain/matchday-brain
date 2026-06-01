# Matchday Brain – X mention content engine update

Adds opt-in X handle mention post ideas to `/admin/content`.

Key updates:
- Sanitises saved X handles before storing.
- Adds consent helper text under the X handle field.
- Adds a Player mentions section in the admin content engine.
- Generates spotlight, recent caller, per-match mention pack, and post-result mention ideas.
- Keeps all posting manual: copy post / open in X / save to planner.

Upload the full package to GitHub, or at minimum replace:
- `app.py`
- `templates/match.html`
- `templates/admin_content.html`
- `static/css/app.css`

Do not upload `.venv`, `.env`, or `__pycache__`.
