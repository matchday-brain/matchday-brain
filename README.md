# Invictus Outdoor Living

Commercial-style Flask website for the Invictus Outdoor Living BBQ / outdoor kitchen configurator.

## Local run

```cmd
cd /d C:\apps\invictus_outdoor_living_commercial
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## GitHub / Render

This project is already structured for Render:

```text
app.py
Procfile
requirements.txt
runtime.txt
templates/
static/
data/
```

Render start command:

```text
gunicorn app:app
```

## Admin

```text
/admin
```
