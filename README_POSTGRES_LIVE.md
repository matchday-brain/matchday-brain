# Matchday Brain live Postgres build

This build supports local SQLite for development and Railway Postgres for live entries.

## Railway setup

1. In Railway, add a Postgres database to the same project.
2. Railway should automatically provide `DATABASE_URL` to the web service. If it does not, copy the database connection URL into the web service variables as `DATABASE_URL`.
3. Keep these web service variables set:

```text
SECRET_KEY=long-random-private-value
ADMIN_PASSWORD=your-private-admin-password
BASE_URL=https://matchdaybrain.com
APP_PUBLIC_BASE_URL=https://matchdaybrain.com
FLASK_DEBUG=0
ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF=60
AUTO_SEED_FIXTURES=1
```

## What happens on first deploy

When the app starts, it creates the Postgres tables and, if the fixtures table is empty, loads the clean World Cup schedule and countries only. It does not create fake predictions or fake posts.

## Backup/export

Admin area includes:

```text
/admin/export/entries.csv
```

Use this regularly once real entries start coming in.

## X handle field

The prediction form now shows a fixed `@` prefix. Users type only their handle. The app stores the handle cleanly without `@`, and the content engine adds the `@` back when generating mention posts.
