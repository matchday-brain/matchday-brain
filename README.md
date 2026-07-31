# Invictus Outdoor Living — Classy Multi-Page Website

Pages included:

- `/` — premium homepage
- `/range` — BBQ collection
- `/bespoke` — bespoke BBQ configurator and estimate
- `/gallery` — lifestyle inspiration
- `/about` — brand and manufacturing story
- `/contact` — enquiry page

## Run locally

```cmd
cd /d C:\apps\invictus_outdoor_living_classic
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## GitHub / Render

Upload the contents of this folder to the root of the GitHub repository.

Render start command:

```text
gunicorn app:app
```
