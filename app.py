import os
import sqlite3
import hashlib
import random
import re
import csv
import io
import unicodedata
import io
import textwrap
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, has_request_context, redirect, render_template, request, session, url_for, Response
)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageFilter
except Exception:  # Pillow is installed from requirements in production.
    Image = ImageDraw = ImageFont = ImageFilter = None

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "matchday.sqlite")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
UK_TZ = ZoneInfo("Europe/London")


class HybridRow(dict):
    """Dict row that also supports row[0] for COUNT(*) style queries."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class PgResult:
    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class PgConn:
    def __init__(self):
        import psycopg2
        self._conn = psycopg2.connect(DATABASE_URL)

    def _translate(self, sql):
        sql = sql.replace("?", "%s")
        sql = sql.replace("datetime(", "(")
        sql = sql.replace("DELETE FROM sqlite_sequence WHERE name IN ('posts','entries','fixtures','clubs')", "SELECT 1")
        return sql

    def execute(self, sql, params=()):
        sql = self._translate(sql)
        lower = sql.strip().lower()
        returning_id = False
        if lower.startswith("insert into entries") and "returning" not in lower:
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
            returning_id = True
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        rows = []
        lastrowid = None
        if cur.description:
            cols = [c[0] for c in cur.description]
            for raw in cur.fetchall():
                rows.append(HybridRow({cols[i]: raw[i] for i in range(len(cols))}))
            if returning_id and rows:
                lastrowid = rows[0][0]
        cur.close()
        return PgResult(rows, lastrowid)

    def executescript(self, script):
        for part in script.split(';'):
            if part.strip():
                self.execute(part)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

LEAGUES = {"wc2026": "World Cup 2026"}
MOODS = ["Buzzing", "Confident", "Nervous", "Deluded", "No idea but I am here"]

TEAM_FLAGS = {
    "Mexico": "🇲🇽", "South Africa": "🇿🇦", "South Korea": "🇰🇷", "Czech Republic": "🇨🇿",
    "Canada": "🇨🇦", "Bosnia & Herzegovina": "🇧🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭",
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴",
    "United States": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺", "Turkey": "🇹🇷",
    "Germany": "🇩🇪", "Curacao": "🇨🇼", "Curaçao": "🇨🇼", "Ivory Coast": "🇨🇮", "Ecuador": "🇪🇨",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Sweden": "🇸🇪", "Tunisia": "🇹🇳",
    "Belgium": "🇧🇪", "Egypt": "🇪🇬", "Iran": "🇮🇷", "New Zealand": "🇳🇿",
    "Spain": "🇪🇸", "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Iraq": "🇮🇶", "Norway": "🇳🇴",
    "Argentina": "🇦🇷", "Algeria": "🇩🇿", "Austria": "🇦🇹", "Jordan": "🇯🇴",
    "Portugal": "🇵🇹", "DR Congo": "🇨🇩", "Congo DR": "🇨🇩", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴",
    "England": "🏴", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
}

TEAM_CODES = {
    "Mexico": "MEX", "South Africa": "RSA", "South Korea": "KOR", "Czech Republic": "CZE",
    "Canada": "CAN", "Bosnia & Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
    "Brazil": "BRA", "Morocco": "MAR", "Haiti": "HAI", "Scotland": "SCO",
    "United States": "USA", "Paraguay": "PAR", "Australia": "AUS", "Turkey": "TUR",
    "Germany": "GER", "Curacao": "CUW", "Curaçao": "CUW", "Ivory Coast": "CIV", "Ecuador": "ECU",
    "Netherlands": "NED", "Japan": "JPN", "Sweden": "SWE", "Tunisia": "TUN",
    "Belgium": "BEL", "Egypt": "EGY", "Iran": "IRN", "New Zealand": "NZL",
    "Spain": "ESP", "Cape Verde": "CPV", "Saudi Arabia": "KSA", "Uruguay": "URU",
    "France": "FRA", "Senegal": "SEN", "Iraq": "IRQ", "Norway": "NOR",
    "Argentina": "ARG", "Algeria": "ALG", "Austria": "AUT", "Jordan": "JOR",
    "Portugal": "POR", "DR Congo": "COD", "Congo DR": "COD", "Uzbekistan": "UZB", "Colombia": "COL",
    "England": "ENG", "Croatia": "CRO", "Ghana": "GHA", "Panama": "PAN",
}

TEAM_FLAG_CODES = {
    "Mexico": "mx", "South Africa": "za", "South Korea": "kr", "Czech Republic": "cz",
    "Canada": "ca", "Bosnia & Herzegovina": "ba", "Qatar": "qa", "Switzerland": "ch",
    "Brazil": "br", "Morocco": "ma", "Haiti": "ht", "Scotland": "gb-sct",
    "United States": "us", "Paraguay": "py", "Australia": "au", "Turkey": "tr",
    "Germany": "de", "Curacao": "cw", "Curaçao": "cw", "Ivory Coast": "ci", "Ecuador": "ec",
    "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
    "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz",
    "Spain": "es", "Cape Verde": "cv", "Saudi Arabia": "sa", "Uruguay": "uy",
    "France": "fr", "Senegal": "sn", "Iraq": "iq", "Norway": "no",
    "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo",
    "Portugal": "pt", "DR Congo": "cd", "Congo DR": "cd", "Uzbekistan": "uz", "Colombia": "co",
    "England": "gb-eng", "Croatia": "hr", "Ghana": "gh", "Panama": "pa",
}

GROUPS = {
    "Group A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "Group B": ["Canada", "Bosnia & Herzegovina", "Qatar", "Switzerland"],
    "Group C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "Group D": ["United States", "Paraguay", "Australia", "Turkey"],
    "Group E": ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
    "Group F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "Group G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "Group H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "Group I": ["France", "Senegal", "Iraq", "Norway"],
    "Group J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "Group K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "Group L": ["England", "Croatia", "Ghana", "Panama"],
}

# Kick-off times are entered as UK local time, then stored as UTC ISO strings.
WORLD_CUP_FIXTURES_UK = [
    ("Group A", "Mexico", "South Africa", "2026-06-11 20:00", "Mexico City, Mexico"),
    ("Group A", "South Korea", "Czech Republic", "2026-06-12 03:00", "Zapopan, Mexico"),
    ("Group B", "Canada", "Bosnia & Herzegovina", "2026-06-12 20:00", "Toronto, Canada"),
    ("Group D", "United States", "Paraguay", "2026-06-13 02:00", "Los Angeles, USA"),
    ("Group B", "Qatar", "Switzerland", "2026-06-13 20:00", "Santa Clara, USA"),
    ("Group C", "Brazil", "Morocco", "2026-06-13 23:00", "New Jersey, USA"),
    ("Group C", "Haiti", "Scotland", "2026-06-14 02:00", "Foxborough, USA"),
    ("Group D", "Australia", "Turkey", "2026-06-14 05:00", "Vancouver, Canada"),
    ("Group E", "Germany", "Curacao", "2026-06-14 18:00", "Houston, USA"),
    ("Group F", "Netherlands", "Japan", "2026-06-14 21:00", "Arlington, USA"),
    ("Group E", "Ivory Coast", "Ecuador", "2026-06-15 00:00", "Philadelphia, USA"),
    ("Group F", "Sweden", "Tunisia", "2026-06-15 03:00", "Guadalupe, Mexico"),
    ("Group H", "Spain", "Cape Verde", "2026-06-15 17:00", "Atlanta, USA"),
    ("Group G", "Belgium", "Egypt", "2026-06-15 20:00", "Seattle, USA"),
    ("Group H", "Saudi Arabia", "Uruguay", "2026-06-15 23:00", "Miami, USA"),
    ("Group G", "Iran", "New Zealand", "2026-06-16 02:00", "Los Angeles, USA"),
    ("Group I", "France", "Senegal", "2026-06-16 20:00", "New Jersey, USA"),
    ("Group I", "Iraq", "Norway", "2026-06-16 23:00", "Foxborough, USA"),
    ("Group J", "Argentina", "Algeria", "2026-06-17 02:00", "Kansas City, USA"),
    ("Group J", "Austria", "Jordan", "2026-06-17 05:00", "Santa Clara, USA"),
    ("Group K", "Portugal", "DR Congo", "2026-06-17 18:00", "Houston, USA"),
    ("Group L", "England", "Croatia", "2026-06-17 21:00", "Arlington, USA"),
    ("Group L", "Ghana", "Panama", "2026-06-18 00:00", "Toronto, Canada"),
    ("Group K", "Uzbekistan", "Colombia", "2026-06-18 03:00", "Mexico City, Mexico"),
    ("Group A", "Czech Republic", "South Africa", "2026-06-18 17:00", "Atlanta, USA"),
    ("Group B", "Switzerland", "Bosnia & Herzegovina", "2026-06-18 20:00", "Los Angeles, USA"),
    ("Group B", "Canada", "Qatar", "2026-06-18 23:00", "Vancouver, Canada"),
    ("Group A", "Mexico", "South Korea", "2026-06-19 02:00", "Zapopan, Mexico"),
    ("Group D", "United States", "Australia", "2026-06-19 20:00", "Seattle, USA"),
    ("Group C", "Scotland", "Morocco", "2026-06-19 23:00", "Foxborough, USA"),
    ("Group C", "Brazil", "Haiti", "2026-06-20 01:30", "Philadelphia, USA"),
    ("Group D", "Turkey", "Paraguay", "2026-06-20 04:00", "Santa Clara, USA"),
    ("Group F", "Netherlands", "Sweden", "2026-06-20 18:00", "Houston, USA"),
    ("Group E", "Germany", "Ivory Coast", "2026-06-20 21:00", "Toronto, Canada"),
    ("Group E", "Ecuador", "Curacao", "2026-06-21 01:00", "Kansas City, USA"),
    ("Group F", "Tunisia", "Japan", "2026-06-21 05:00", "Guadalupe, Mexico"),
    ("Group H", "Spain", "Saudi Arabia", "2026-06-21 17:00", "Atlanta, USA"),
    ("Group G", "Belgium", "Iran", "2026-06-21 20:00", "Los Angeles, USA"),
    ("Group H", "Uruguay", "Cape Verde", "2026-06-21 23:00", "Miami, USA"),
    ("Group G", "New Zealand", "Egypt", "2026-06-22 02:00", "Vancouver, Canada"),
    ("Group J", "Argentina", "Austria", "2026-06-22 18:00", "Arlington, USA"),
    ("Group I", "France", "Iraq", "2026-06-22 22:00", "Philadelphia, USA"),
    ("Group I", "Norway", "Senegal", "2026-06-23 01:00", "Toronto, Canada"),
    ("Group J", "Jordan", "Algeria", "2026-06-23 04:00", "Santa Clara, USA"),
    ("Group K", "Portugal", "Uzbekistan", "2026-06-23 18:00", "Houston, USA"),
    ("Group L", "England", "Ghana", "2026-06-23 21:00", "Foxborough, USA"),
    ("Group L", "Panama", "Croatia", "2026-06-24 00:00", "Foxborough, USA"),
    ("Group K", "Colombia", "DR Congo", "2026-06-24 03:00", "Zapopan, Mexico"),
    ("Group B", "Switzerland", "Canada", "2026-06-24 20:00", "Vancouver, Canada"),
    ("Group B", "Bosnia & Herzegovina", "Qatar", "2026-06-24 20:00", "Seattle, USA"),
    ("Group C", "Morocco", "Haiti", "2026-06-24 23:00", "Atlanta, USA"),
    ("Group C", "Scotland", "Brazil", "2026-06-24 23:00", "Miami, USA"),
    ("Group A", "South Africa", "South Korea", "2026-06-25 02:00", "Guadalupe, Mexico"),
    ("Group A", "Czech Republic", "Mexico", "2026-06-25 02:00", "Mexico City, Mexico"),
    ("Group E", "Curacao", "Ivory Coast", "2026-06-25 21:00", "Philadelphia, USA"),
    ("Group E", "Ecuador", "Germany", "2026-06-25 21:00", "New Jersey, USA"),
    ("Group F", "Tunisia", "Netherlands", "2026-06-26 00:00", "Kansas City, USA"),
    ("Group F", "Japan", "Sweden", "2026-06-26 00:00", "Arlington, USA"),
    ("Group D", "Turkey", "United States", "2026-06-26 03:00", "Los Angeles, USA"),
    ("Group D", "Paraguay", "Australia", "2026-06-26 03:00", "Santa Clara, USA"),
    ("Group I", "Norway", "France", "2026-06-26 20:00", "Foxborough, USA"),
    ("Group I", "Senegal", "Iraq", "2026-06-26 20:00", "Toronto, Canada"),
    ("Group H", "Cape Verde", "Saudi Arabia", "2026-06-27 01:00", "Houston, USA"),
    ("Group H", "Uruguay", "Spain", "2026-06-27 01:00", "Zapopan, Mexico"),
    ("Group G", "New Zealand", "Belgium", "2026-06-27 04:00", "Vancouver, Canada"),
    ("Group G", "Egypt", "Iran", "2026-06-27 04:00", "Seattle, USA"),
    ("Group L", "Panama", "England", "2026-06-27 22:00", "New Jersey, USA"),
    ("Group L", "Croatia", "Ghana", "2026-06-27 22:00", "Philadelphia, USA"),
    ("Group K", "Colombia", "Portugal", "2026-06-28 00:30", "Miami, USA"),
    ("Group K", "DR Congo", "Uzbekistan", "2026-06-28 00:30", "Atlanta, USA"),
    ("Group J", "Algeria", "Austria", "2026-06-28 03:00", "Kansas City, USA"),
    ("Group J", "Jordan", "Argentina", "2026-06-28 03:00", "Arlington, USA"),
]

DEMO_PLAYERS = [
    ("Jim", "jburgoine", "England", "The Navigation Inn"),
    ("Ash", "awaydaysash", "Brazil", "The Red Lion"),
    ("Macca", "maccascores", "Scotland", "The Navigation Inn"),
    ("Leah", "leahfootball", "France", "High Street Tap"),
    ("Ben", "benmatchday", "Germany", "The Red Lion"),
    ("Sophie", "sophietalksball", "Spain", "The Corner Flag"),
    ("Ryan", "ryanaway", "Argentina", "Station Arms"),
    ("Callum", "calpredicts", "Portugal", "Market Tavern"),
    ("Jess", "jessonthewing", "Netherlands", "The Corner Flag"),
    ("Dan", "danfromblock12", "United States", "The Navigation Inn"),
    ("Rob", "robknowsball", "Uruguay", "The Red Lion"),
    ("Amy", "amymatchday", "Canada", "Market Tavern"),
    ("Gaz", "gaz_pints_pies", "Mexico", "Station Arms"),
    ("Nina", "ninafootball", "Morocco", "High Street Tap"),
    ("Pete", "peteontour", "Australia", "The Corner Flag"),
    ("Mo", "mo90mins", "Croatia", "Market Tavern"),
    ("Ellis", "ellis_fans", "Ghana", "The Navigation Inn"),
]

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF = int(os.getenv("ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF", "60"))


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uk_to_utc_iso(value):
    local = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=UK_TZ)
    return local.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def format_kickoff(value):
    if not value:
        return "TBC"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        uk = dt.astimezone(UK_TZ)
        return uk.strftime("%a %d %b · %H:%M UK")
    except Exception:
        return value[:16].replace("T", " ")




def parse_utc_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def entry_deadline_utc(fixture):
    kickoff = parse_utc_datetime(fixture["kickoff_utc"] if hasattr(fixture, "keys") else fixture.get("kickoff_utc"))
    if kickoff is None:
        return None
    return kickoff - timedelta(seconds=ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF)


def entry_is_open(fixture):
    if fixture is None:
        return False
    if str(fixture["status"] if hasattr(fixture, "keys") else fixture.get("status", "")).lower() not in ("", "scheduled", "open"):
        return False
    deadline = entry_deadline_utc(fixture)
    if deadline is None:
        return False
    return datetime.now(timezone.utc) < deadline


def format_entry_deadline(fixture):
    deadline = entry_deadline_utc(fixture)
    if deadline is None:
        return "before kick-off"
    return deadline.astimezone(UK_TZ).strftime("%a %d %b · %H:%M:%S UK")

def get_db():
    if USE_POSTGRES:
        return PgConn()
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def slugify(value):
    value = unicodedata.normalize("NFKD", (value or "")).encode("ascii", "ignore").decode("ascii")
    value = value.strip().lower()
    allowed = []
    last_dash = False
    for ch in value:
        if ch.isalnum():
            allowed.append(ch)
            last_dash = False
        elif not last_dash:
            allowed.append("-")
            last_dash = True
    return "".join(allowed).strip("-") or "team"


def team_flag(team_name):
    return TEAM_FLAGS.get(team_name, "⚽")


def team_flag_code(team_name):
    return TEAM_FLAG_CODES.get(team_name or "", "")


def team_flag_url(team_name):
    code = team_flag_code(team_name)
    if not code:
        return ""
    # External flag images avoid the Windows emoji-flag issue where flags render as two letters.
    return f"https://flagcdn.com/w80/{code}.png"


def team_code(team_name):
    return TEAM_CODES.get(team_name, (team_name or "").upper()[:3])


def logo_for_team(team_name):
    filename = f"{slugify(team_name)}.png"
    path = os.path.join(APP_DIR, "static", "logos", filename)
    if os.path.exists(path):
        return filename
    return ""


def ensure_column(conn, table, column, definition):
    if USE_POSTGRES:
        existing = {
            row["column_name"] for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name=?",
                (table,),
            ).fetchall()
        }
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = get_db()
    if USE_POSTGRES:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clubs (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                short_name TEXT,
                slug TEXT NOT NULL UNIQUE,
                league_name TEXT,
                logo_filename TEXT,
                primary_color TEXT DEFAULT '#111827',
                secondary_color TEXT DEFAULT '#facc15',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fixtures (
                id SERIAL PRIMARY KEY,
                external_id TEXT UNIQUE,
                league_id TEXT,
                league_name TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_slug TEXT,
                away_slug TEXT,
                kickoff_utc TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                home_score INTEGER,
                away_score INTEGER,
                source TEXT DEFAULT 'manual',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entries (
                id SERIAL PRIMARY KEY,
                fixture_id INTEGER NOT NULL REFERENCES fixtures(id),
                player_name TEXT NOT NULL,
                x_handle TEXT,
                email TEXT,
                club_supporting TEXT,
                pub_group TEXT,
                pred_home_goals INTEGER NOT NULL,
                pred_away_goals INTEGER NOT NULL,
                first_goal_minute INTEGER,
                attendance_guess INTEGER,
                mood TEXT,
                ip_hash TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                scheduled_at TEXT,
                status TEXT DEFAULT 'draft',
                link_url TEXT,
                image_note TEXT,
                created_at TEXT NOT NULL,
                posted_at TEXT
            );
            """
        )
    else:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS clubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                short_name TEXT,
                slug TEXT NOT NULL UNIQUE,
                league_name TEXT,
                logo_filename TEXT,
                primary_color TEXT DEFAULT '#111827',
                secondary_color TEXT DEFAULT '#facc15',
                active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fixtures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                league_id TEXT,
                league_name TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_slug TEXT,
                away_slug TEXT,
                kickoff_utc TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                home_score INTEGER,
                away_score INTEGER,
                source TEXT DEFAULT 'manual',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fixture_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                x_handle TEXT,
                email TEXT,
                club_supporting TEXT,
                pub_group TEXT,
                pred_home_goals INTEGER NOT NULL,
                pred_away_goals INTEGER NOT NULL,
                first_goal_minute INTEGER,
                attendance_guess INTEGER,
                mood TEXT,
                ip_hash TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (fixture_id) REFERENCES fixtures(id)
            );
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                scheduled_at TEXT,
                status TEXT DEFAULT 'draft',
                link_url TEXT,
                image_note TEXT,
                created_at TEXT NOT NULL,
                posted_at TEXT
            );
            """
        )
    ensure_column(conn, "fixtures", "venue", "TEXT")
    ensure_column(conn, "fixtures", "actual_first_goal_minute", "INTEGER")
    conn.commit()
    conn.close()


def seed_worldcup_schedule(clear=False):
    """Load countries and group-stage fixtures only. No fake entries/posts."""
    init_db()
    conn = get_db()
    if clear:
        conn.execute("DELETE FROM posts")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM fixtures")
        conn.execute("DELETE FROM clubs")
        if not USE_POSTGRES:
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('posts','entries','fixtures','clubs')")
    for group_name, teams in GROUPS.items():
        for team in teams:
            ensure_club(conn, team, "World Cup 2026")
    for group_name, home, away, kickoff_uk, venue in WORLD_CUP_FIXTURES_UK:
        home_slug = ensure_club(conn, home, "World Cup 2026")
        away_slug = ensure_club(conn, away, "World Cup 2026")
        external_id = f"wc2026-{slugify(home)}-{slugify(away)}-{kickoff_uk.replace(' ', '-')}"
        conn.execute(
            """
            INSERT INTO fixtures (external_id, league_id, league_name, home_team, away_team, home_slug, away_slug, kickoff_utc, venue, source, updated_at)
            VALUES (?, 'wc2026', ?, ?, ?, ?, ?, ?, ?, 'worldcup_static', ?)
            ON CONFLICT(external_id) DO UPDATE SET
                league_name=excluded.league_name,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                home_slug=excluded.home_slug,
                away_slug=excluded.away_slug,
                kickoff_utc=excluded.kickoff_utc,
                venue=excluded.venue,
                updated_at=excluded.updated_at
            """,
            (external_id, group_name, home, away, home_slug, away_slug, uk_to_utc_iso(kickoff_uk), venue, utc_now_iso()),
        )
    conn.commit()
    stats = {
        "clubs": conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
        "fixtures": conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0],
        "entries": conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
    }
    conn.close()
    return stats


def ensure_club(conn, team_name, league_name="World Cup 2026"):
    slug = slugify(team_name)
    conn.execute(
        """
        INSERT INTO clubs (name, short_name, slug, league_name, logo_filename, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            short_name=excluded.short_name,
            league_name=excluded.league_name,
            logo_filename=CASE WHEN clubs.logo_filename IS NULL OR clubs.logo_filename='' THEN excluded.logo_filename ELSE clubs.logo_filename END,
            active=1
        """,
        (team_name, team_code(team_name), slug, league_name, logo_for_team(team_name), utc_now_iso()),
    )
    return slug


def admin_required():
    if not session.get("admin_ok"):
        abort(403)


def ip_hash():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:20]


def score_entry(entry, fixture):
    if fixture["home_score"] is None or fixture["away_score"] is None:
        return None
    ph = int(entry["pred_home_goals"])
    pa = int(entry["pred_away_goals"])
    ah = int(fixture["home_score"])
    aa = int(fixture["away_score"])

    points = 0
    reasons = []
    if ph == ah and pa == aa:
        points += 5
        reasons.append("exact score")
    elif (ph - pa) == (ah - aa):
        points += 2
        reasons.append("goal difference")

    pred_result = 1 if ph > pa else -1 if ph < pa else 0
    actual_result = 1 if ah > aa else -1 if ah < aa else 0
    if pred_result == actual_result:
        points += 2
        reasons.append("right result")

    tie_delta = None
    if fixture["actual_first_goal_minute"] is not None and entry["first_goal_minute"] is not None:
        tie_delta = abs(int(entry["first_goal_minute"]) - int(fixture["actual_first_goal_minute"]))
        reasons.append(f"{tie_delta} min tie-breaker gap")

    return {"points": points, "tie_delta": tie_delta, "reasons": ", ".join(reasons) or "no points"}


def public_base_url():
    return (
        os.getenv("APP_PUBLIC_BASE_URL")
        or os.getenv("BASE_URL")
        or request.url_root.rstrip("/")
    ).rstrip("/")


def absolute_url(path="/"):
    if not path.startswith("/"):
        path = "/" + path
    return public_base_url() + path


def default_meta_description():
    return (
        "Matchday Brain is a free football prediction game for the 2026 global tournament. "
        "Pick the score, guess the first goal and play for your country before kick-off."
    )


@app.context_processor
def inject_globals():
    return {
        "MOODS": MOODS,
        "LEAGUES": LEAGUES,
        "team_flag": team_flag,
        "team_flag_code": team_flag_code,
        "team_flag_url": team_flag_url,
        "team_code": team_code,
        "format_kickoff": format_kickoff,
        "entry_is_open": entry_is_open,
        "format_entry_deadline": format_entry_deadline,
        "ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF": ENTRY_CLOSE_SECONDS_BEFORE_KICKOFF,
        "public_base_url": public_base_url,
        "absolute_url": absolute_url,
        "default_meta_description": default_meta_description,
    }


@app.route("/")
def index():
    conn = get_db()
    fixtures = conn.execute(
        """
        SELECT f.*, (SELECT COUNT(*) FROM entries e WHERE e.fixture_id=f.id) AS entry_count
        FROM fixtures f
        ORDER BY datetime(f.kickoff_utc) ASC
        LIMIT 120
        """
    ).fetchall()
    conn.close()
    return render_template(
        "index.html",
        fixtures=fixtures,
        title="Matchday Brain | World Cup 2026 Football Prediction Game",
        meta_description=default_meta_description(),
        canonical_url=absolute_url(url_for("index")),
        og_image=absolute_url(url_for("og_home_image")),
    )


@app.route("/match/<int:fixture_id>", methods=["GET", "POST"])
def match(fixture_id):
    conn = get_db()
    fixture = conn.execute("SELECT * FROM fixtures WHERE id=?", (fixture_id,)).fetchone()
    if not fixture:
        conn.close()
        abort(404)

    entry_open = entry_is_open(fixture)

    if request.method == "POST":
        if not entry_open:
            flash("Entries for this match are closed. Predictions lock before kick-off.", "error")
            conn.close()
            return redirect(url_for("match", fixture_id=fixture_id))

        player_name = request.form.get("player_name", "").strip()
        x_handle = clean_x_handle(request.form.get("x_handle", ""))
        email = request.form.get("email", "").strip()
        club_supporting = request.form.get("club_supporting", "").strip()
        pub_group = ""
        mood = request.form.get("mood", "").strip()

        try:
            pred_home_goals = int(request.form.get("pred_home_goals", ""))
            pred_away_goals = int(request.form.get("pred_away_goals", ""))
        except ValueError:
            pred_home_goals = pred_away_goals = -1

        first_goal_minute_raw = request.form.get("first_goal_minute", "").strip()
        first_goal_minute = int(first_goal_minute_raw) if first_goal_minute_raw.isdigit() else None

        if not player_name or pred_home_goals < 0 or pred_away_goals < 0:
            flash("Add your name and a valid score prediction.", "error")
        elif first_goal_minute is None or first_goal_minute < 1 or first_goal_minute > 120:
            flash("Add a first-goal minute between 1 and 120 for the tie-breaker.", "error")
        else:
            cur = conn.execute(
                """
                INSERT INTO entries (
                    fixture_id, player_name, x_handle, email, club_supporting, pub_group,
                    pred_home_goals, pred_away_goals, first_goal_minute, attendance_guess,
                    mood, ip_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    fixture_id, player_name, x_handle, email, club_supporting, pub_group,
                    pred_home_goals, pred_away_goals, first_goal_minute,
                    mood, ip_hash(), utc_now_iso()
                ),
            )
            conn.commit()
            entry_id = cur.lastrowid
            conn.close()
            return redirect(url_for("thanks", entry_id=entry_id))

    entries = conn.execute(
        "SELECT * FROM entries WHERE fixture_id=? ORDER BY datetime(created_at) DESC LIMIT 25",
        (fixture_id,),
    ).fetchall()
    clubs = conn.execute("SELECT * FROM clubs WHERE active=1 ORDER BY name").fetchall()
    total_predictions = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    fixture_entries = conn.execute("SELECT COUNT(*) FROM entries WHERE fixture_id=?", (fixture_id,)).fetchone()[0]
    score_rows = conn.execute(
        """
        SELECT pred_home_goals, pred_away_goals, COUNT(*) AS entries
        FROM entries
        WHERE fixture_id=?
        GROUP BY pred_home_goals, pred_away_goals
        ORDER BY entries DESC, pred_home_goals DESC, pred_away_goals ASC
        LIMIT 3
        """,
        (fixture_id,),
    ).fetchall()
    country_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral') AS country, COUNT(*) AS entries
        FROM entries
        GROUP BY COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral')
        ORDER BY entries DESC, country ASC
        LIMIT 5
        """
    ).fetchall()
    home_backers = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE fixture_id=? AND club_supporting=?",
        (fixture_id, fixture["home_team"]),
    ).fetchone()[0]
    away_backers = conn.execute(
        "SELECT COUNT(*) FROM entries WHERE fixture_id=? AND club_supporting=?",
        (fixture_id, fixture["away_team"]),
    ).fetchone()[0]
    conn.close()
    return render_template(
        "match.html",
        fixture=fixture,
        entries=entries,
        clubs=clubs,
        total_predictions=total_predictions,
        fixture_entries=fixture_entries,
        score_rows=score_rows,
        country_rows=country_rows,
        home_backers=home_backers,
        away_backers=away_backers,
        entry_open=entry_open,
        entry_deadline=format_entry_deadline(fixture),
        title=f"{fixture['home_team']} v {fixture['away_team']} Prediction | Matchday Brain",
        meta_description=(
            f"Make your {fixture['home_team']} v {fixture['away_team']} football prediction. "
            "Pick the score, guess the first goal and back your country before kick-off."
        ),
        canonical_url=absolute_url(url_for("match", fixture_id=fixture_id)),
        og_image=absolute_url(url_for("og_match_image", fixture_id=fixture_id)),
    )


@app.route("/thanks/<int:entry_id>")
def thanks(entry_id):
    conn = get_db()
    row = conn.execute(
        """
        SELECT e.*, f.home_team, f.away_team, f.kickoff_utc
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        WHERE e.id=?
        """,
        (entry_id,),
    ).fetchone()
    conn.close()
    if not row:
        abort(404)

    match_url = f"{public_base_url()}{url_for('match', fixture_id=row['fixture_id'])}"
    text = (
        f"I have backed {row['home_team']} {row['pred_home_goals']}-{row['pred_away_goals']} "
        f"{row['away_team']} on Matchday Brain. First goal tie-breaker: {row['first_goal_minute']}' minute. "
        f"Think you know better? {match_url}"
    )
    text = add_x_hashtags(text, row['home_team'], row['away_team'], row.get('club_supporting'))
    share_url = f"https://twitter.com/intent/tweet?text={quote_plus(text)}"
    return render_template(
        "thanks.html",
        row=row,
        share_url=share_url,
        match_url=match_url,
        title="Prediction saved | Matchday Brain",
        meta_description="Your Matchday Brain prediction has been saved. Share your football score call and challenge other fans to play.",
        canonical_url=absolute_url(url_for("thanks", entry_id=entry_id)),
        noindex=True,
    )


@app.route("/leaderboard")
def leaderboard():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT e.*, f.home_team, f.away_team, f.home_score, f.away_score, f.kickoff_utc, f.status, f.actual_first_goal_minute
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        ORDER BY datetime(e.created_at) DESC
        LIMIT 500
        """
    ).fetchall()
    pub_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(pub_group), ''), 'No group') AS pub_group, COUNT(*) AS entries
        FROM entries
        WHERE TRIM(COALESCE(pub_group, '')) <> ''
        GROUP BY COALESCE(NULLIF(TRIM(pub_group), ''), 'No group')
        ORDER BY entries DESC, pub_group ASC
        LIMIT 20
        """
    ).fetchall()
    club_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(club_supporting), ''), 'No country') AS club_supporting, COUNT(*) AS entries
        FROM entries
        GROUP BY COALESCE(NULLIF(TRIM(club_supporting), ''), 'No country')
        ORDER BY entries DESC, club_supporting ASC
        LIMIT 20
        """
    ).fetchall()
    conn.close()

    scored = []
    for row in rows:
        s = score_entry(row, row)
        points = s["points"] if s else 0
        tie_delta = s["tie_delta"] if s and s["tie_delta"] is not None else 999
        scored.append({"row": row, "score": s, "points": points, "tie_delta": tie_delta})
    scored.sort(key=lambda x: (x["points"], -x["tie_delta"], x["row"]["created_at"]), reverse=True)

    return render_template(
        "leaderboard.html",
        scored=scored,
        pub_rows=pub_rows,
        club_rows=club_rows,
        title="Country Leaderboard | Matchday Brain",
        meta_description="See the Matchday Brain country leaderboard and the latest football prediction standings for the 2026 global tournament.",
        canonical_url=absolute_url(url_for("leaderboard")),
        og_image=absolute_url(url_for("og_home_image")),
    )


@app.route("/about")
def about():
    return render_template(
        "about.html",
        title="About Matchday Brain | Football Prediction Game",
        meta_description="Matchday Brain is a fan-made football prediction game where supporters pick scores, guess first-goal minutes and compete on country leaderboards.",
        canonical_url=absolute_url(url_for("about")),
        og_image=absolute_url(url_for("og_home_image")),
    )


@app.route("/privacy")
def privacy():
    return render_template(
        "privacy.html",
        title="Privacy Policy | Matchday Brain",
        meta_description="Read the Matchday Brain privacy policy for the football prediction game.",
        canonical_url=absolute_url(url_for("privacy")),
        noindex=False,
    )


@app.route("/terms")
def terms():
    return render_template(
        "terms.html",
        title="Terms | Matchday Brain",
        meta_description="Read the Matchday Brain terms for the football prediction game.",
        canonical_url=absolute_url(url_for("terms")),
        noindex=False,
    )


@app.route("/robots.txt")
def robots_txt():
    body = f"""User-agent: *
Allow: /
Disallow: /admin
Disallow: /thanks/

Sitemap: {absolute_url('/sitemap.xml')}
"""
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    conn = get_db()
    fixtures = conn.execute("SELECT id, updated_at, kickoff_utc FROM fixtures ORDER BY datetime(kickoff_utc) ASC LIMIT 500").fetchall()
    conn.close()
    urls = [
        (absolute_url(url_for("index")), "daily", "1.0"),
        (absolute_url(url_for("leaderboard")), "hourly", "0.8"),
        (absolute_url(url_for("about")), "monthly", "0.5"),
        (absolute_url(url_for("privacy")), "monthly", "0.3"),
        (absolute_url(url_for("terms")), "monthly", "0.3"),
    ]
    for f in fixtures:
        urls.append((absolute_url(url_for("match", fixture_id=f["id"])), "daily", "0.7"))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    today = datetime.now(timezone.utc).date().isoformat()
    for loc, changefreq, priority in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), mimetype="application/xml")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == os.getenv("ADMIN_PASSWORD", "change-this-password"):
            session["admin_ok"] = True
            return redirect(url_for("admin_home"))
        flash("Wrong password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
def admin_home():
    admin_required()
    conn = get_db()
    stats = {
        "fixtures": conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0],
        "entries": conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
        "clubs": conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
    }
    latest = conn.execute(
        """
        SELECT e.*, f.home_team, f.away_team
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        ORDER BY datetime(e.created_at) DESC LIMIT 20
        """
    ).fetchall()
    conn.close()
    return render_template("admin.html", stats=stats, latest=latest)


@app.route("/admin/fixtures", methods=["GET", "POST"])
def admin_fixtures():
    admin_required()
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "manual_add":
            league_name = request.form.get("league_name", "World Cup 2026").strip()
            home_team = request.form.get("home_team", "").strip()
            away_team = request.form.get("away_team", "").strip()
            kickoff_utc = request.form.get("kickoff_utc", "").strip()
            venue = request.form.get("venue", "").strip()
            if home_team and away_team and kickoff_utc:
                home_slug = ensure_club(conn, home_team, league_name)
                away_slug = ensure_club(conn, away_team, league_name)
                conn.execute(
                    """
                    INSERT INTO fixtures (league_name, home_team, away_team, home_slug, away_slug, kickoff_utc, venue, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)
                    """,
                    (league_name, home_team, away_team, home_slug, away_slug, kickoff_utc, venue, utc_now_iso()),
                )
                conn.commit()
                flash("Fixture added.", "ok")
            else:
                flash("Home team, away team and kick-off are required.", "error")

        elif action == "update_result":
            fixture_id = int(request.form.get("fixture_id"))
            status = request.form.get("status", "scheduled")
            home_score = request.form.get("home_score", "").strip()
            away_score = request.form.get("away_score", "").strip()
            first_goal = request.form.get("actual_first_goal_minute", "").strip()
            hs = int(home_score) if home_score.isdigit() else None
            aw = int(away_score) if away_score.isdigit() else None
            fg = int(first_goal) if first_goal.isdigit() else None
            conn.execute(
                "UPDATE fixtures SET status=?, home_score=?, away_score=?, actual_first_goal_minute=?, updated_at=? WHERE id=?",
                (status, hs, aw, fg, utc_now_iso(), fixture_id),
            )
            conn.commit()
            flash("Result updated.", "ok")

        return redirect(url_for("admin_fixtures"))

    fixtures = conn.execute(
        """
        SELECT f.*, (SELECT COUNT(*) FROM entries e WHERE e.fixture_id=f.id) AS entry_count
        FROM fixtures f
        ORDER BY datetime(f.kickoff_utc) ASC
        LIMIT 140
        """
    ).fetchall()
    conn.close()
    return render_template("admin_fixtures.html", fixtures=fixtures)




def uk_date_from_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(UK_TZ).date()
    except Exception:
        return None


def fixture_label(fixture):
    return f"{fixture['home_team']} v {fixture['away_team']}"


def flag_name(team):
    return f"{team_flag(team)} {team}".strip()


def clean_x_handle(value):
    """Return a safe X handle without @, or an empty string.

    X handles use letters, numbers and underscores. Keeping this tight avoids
    malformed mentions making their way into generated post copy.
    """
    value = (value or "").strip().lstrip("@").replace(" ", "")
    allowed = "".join(ch for ch in value if ch.isalnum() or ch == "_")
    return allowed[:15]


def x_mention(value):
    handle = clean_x_handle(value)
    return f"@{handle}" if handle else ""


GLOBAL_X_HASHTAGS = ["#FIFAWorldCup", "#FIFAWC", "#WorldCup2026", "#MatchdayBrain"]

COUNTRY_X_HASHTAGS = {
    "England": ["#ThreeLions", "#ENG"],
    "Scotland": ["#NoScotlandNoParty", "#SCO"],
    "Wales": ["#TogetherStronger", "#WAL"],
    "United States": ["#USMNT", "#USA"],
    "Mexico": ["#ElTri", "#MEX"],
    "Canada": ["#CanMNT", "#CAN"],
    "Brazil": ["#Selecao", "#BRA"],
    "Argentina": ["#VamosArgentina", "#ARG"],
    "France": ["#LesBleus", "#FRA"],
    "Germany": ["#DieMannschaft", "#GER"],
    "Spain": ["#LaRoja", "#ESP"],
    "Portugal": ["#Portugal", "#POR"],
    "Netherlands": ["#Oranje", "#NED"],
    "Belgium": ["#RedDevils", "#BEL"],
    "Croatia": ["#Vatreni", "#CRO"],
    "Uruguay": ["#LaCeleste", "#URU"],
    "Colombia": ["#VamosColombia", "#COL"],
    "Japan": ["#SamuraiBlue", "#JPN"],
    "South Korea": ["#KoreaRepublic", "#KOR"],
    "Australia": ["#Socceroos", "#AUS"],
    "New Zealand": ["#AllWhites", "#NZL"],
    "Morocco": ["#AtlasLions", "#MAR"],
    "Senegal": ["#LionsOfTeranga", "#SEN"],
    "Ghana": ["#BlackStars", "#GHA"],
    "South Africa": ["#BafanaBafana", "#RSA"],
    "Egypt": ["#ThePharaohs", "#EGY"],
    "Tunisia": ["#EaglesOfCarthage", "#TUN"],
    "Algeria": ["#LesFennecs", "#ALG"],
    "Ivory Coast": ["#LesElephants", "#CIV"],
    "Turkey": ["#BizimCocuklar", "#TUR"],
    "Iran": ["#TeamMelli", "#IRN"],
    "Saudi Arabia": ["#GreenFalcons", "#KSA"],
    "Qatar": ["#AlAnnabi", "#QAT"],
    "Switzerland": ["#Nati", "#SUI"],
    "Czech Republic": ["#Czechia", "#CZE"],
    "Norway": ["#Norway", "#NOR"],
    "Sweden": ["#Sverige", "#SWE"],
    "Austria": ["#DasTeam", "#AUT"],
    "Paraguay": ["#Albirroja", "#PAR"],
    "Ecuador": ["#LaTri", "#ECU"],
    "Panama": ["#LosCanaleros", "#PAN"],
    "Haiti": ["#LesGrenadiers", "#HAI"],
    "Bosnia & Herzegovina": ["#Zmajevi", "#BIH"],
    "DR Congo": ["#Leopards", "#COD"],
    "Congo DR": ["#Leopards", "#COD"],
    "Uzbekistan": ["#WhiteWolves", "#UZB"],
    "Jordan": ["#Nashama", "#JOR"],
    "Iraq": ["#LionsOfMesopotamia", "#IRQ"],
    "Cape Verde": ["#BlueSharks", "#CPV"],
    "Curacao": ["#Curacao", "#CUW"],
    "Curaçao": ["#Curacao", "#CUW"],
}


def x_hashtags_for_teams(*teams, extra=None, max_country_tags=4):
    """Return a clean hashtag footer for X posts.

    We keep the global tags on almost every generated post and then add a small
    number of team/country-specific tags so the post reaches the right fan base
    without looking spammy.
    """
    tags = []
    for tag in GLOBAL_X_HASHTAGS:
        if tag not in tags:
            tags.append(tag)
    for team in teams:
        for tag in COUNTRY_X_HASHTAGS.get(str(team or '').strip(), []):
            if tag not in tags and len([t for t in tags if t not in GLOBAL_X_HASHTAGS]) < max_country_tags:
                tags.append(tag)
    for tag in extra or []:
        if tag and tag not in tags:
            tags.append(tag)
    return " ".join(tags)


def add_x_hashtags(body, *teams, extra=None):
    body = (body or '').strip()
    footer = x_hashtags_for_teams(*teams, extra=extra)
    if not footer:
        return body
    existing = {part for part in body.split() if part.startswith('#')}
    new_tags = [tag for tag in footer.split() if tag not in existing]
    if not new_tags:
        return body
    return body + "\n\n" + " ".join(new_tags)


def make_post(title, section, body, link_url="", image_note="", tag="", teams=None, extra_hashtags=None):
    body = add_x_hashtags(body, *(teams or []), extra=extra_hashtags)
    return {
        "title": title,
        "section": section,
        "body": body.strip(),
        "link_url": link_url,
        "image_note": image_note,
        "tag": tag,
    }


def deterministic_prediction(home, away):
    seed = sum(ord(c) for c in f"{home}|{away}|worldcup")
    home_goals = [1, 2, 2, 1, 3, 0][seed % 6]
    away_goals = [0, 1, 1, 2, 1, 0][(seed // 5) % 6]
    first_goal = [9, 14, 18, 22, 27, 34, 41][seed % 7]
    return home_goals, away_goals, first_goal


def build_content_engine():
    """Create copy-and-paste X content from the latest game data."""
    conn = get_db()
    base = public_base_url()
    fixtures = conn.execute(
        """
        SELECT f.*, (SELECT COUNT(*) FROM entries e WHERE e.fixture_id=f.id) AS entry_count
        FROM fixtures f
        ORDER BY datetime(f.kickoff_utc) ASC
        LIMIT 160
        """
    ).fetchall()
    total_entries = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    total_countries = conn.execute("SELECT COUNT(*) FROM clubs WHERE active=1").fetchone()[0]
    active_countries = conn.execute(
        """
        SELECT COUNT(*) FROM (
          SELECT 1 FROM entries
          WHERE TRIM(COALESCE(club_supporting,'')) <> ''
          GROUP BY TRIM(club_supporting)
        )
        """
    ).fetchone()[0]
    country_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral') AS country, COUNT(*) AS entries
        FROM entries
        GROUP BY COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral')
        ORDER BY entries DESC, country ASC
        LIMIT 20
        """
    ).fetchall()
    mood_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(mood), ''), 'Unknown') AS mood, COUNT(*) AS entries
        FROM entries
        GROUP BY COALESCE(NULLIF(TRIM(mood), ''), 'Unknown')
        ORDER BY entries DESC
        LIMIT 5
        """
    ).fetchall()
    latest_entries = conn.execute(
        """
        SELECT e.*, f.home_team, f.away_team
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        ORDER BY datetime(e.created_at) DESC
        LIMIT 8
        """
    ).fetchall()
    mention_entries = conn.execute(
        """
        SELECT e.*, f.home_team, f.away_team, f.kickoff_utc, f.status,
               f.home_score, f.away_score, f.actual_first_goal_minute
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        WHERE TRIM(COALESCE(e.x_handle, '')) <> ''
        ORDER BY datetime(e.created_at) DESC
        LIMIT 40
        """
    ).fetchall()

    today = datetime.now(UK_TZ).date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    fixtures_today = [f for f in fixtures if uk_date_from_iso(f["kickoff_utc"]) == today]
    fixtures_yesterday = [f for f in fixtures if uk_date_from_iso(f["kickoff_utc"]) == yesterday]
    fixtures_tomorrow = [f for f in fixtures if uk_date_from_iso(f["kickoff_utc"]) == tomorrow]
    upcoming = [f for f in fixtures if uk_date_from_iso(f["kickoff_utc"]) and uk_date_from_iso(f["kickoff_utc"]) >= today]
    next_active = fixtures_today or upcoming[:6]

    sections = {
        "live_today": [],
        "yesterday": [],
        "tomorrow": [],
        "we_predict": [],
        "country_race": [],
        "player_mentions": [],
        "match_angles": [],
        "global_hooks": [],
    }

    # Global hooks
    if country_rows:
        top3 = "\n".join([f"{i+1}. {flag_name(r['country'])} — {r['entries']} calls" for i, r in enumerate(country_rows[:3])])
    else:
        top3 = "No countries have entered yet."
    sections["global_hooks"].append(make_post(
        "Global launch / everyone can play",
        "Global hooks",
        f"World Cup prediction game is open.\n\nPick the score. Guess the first-goal minute. Play for your country.\n\n🌍 {total_countries} countries loaded\n⚽ {len(fixtures)} fixtures\n🔥 {total_entries} fan calls already in\n\nPlay here: {base}",
        base,
        "Use the premium homepage screenshot with the country leaderboard.",
        "launch",
    ))
    sections["global_hooks"].append(make_post(
        "Country race teaser",
        "Global hooks",
        f"The early country race is already taking shape.\n\n{top3}\n\nBack your country before kick-off.\n\nPlay here: {base}/leaderboard",
        f"{base}/leaderboard",
        "Use country leaderboard screenshot.",
        "country race",
    ))
    if mood_rows:
        mood_text = ", ".join([f"{r['mood']} ({r['entries']})" for r in mood_rows[:3]])
        sections["global_hooks"].append(make_post(
            "Fan mood pulse",
            "Global hooks",
            f"World Cup fan mood right now:\n\n{mood_text}\n\nMake your call before the next kick-off.\n\nPick score + first goal minute: {base}",
            base,
            "Use fan pulse widget/screenshot.",
            "fan mood",
        ))

    # Live today / opening fallback
    if fixtures_today:
        sections["live_today"].append(make_post(
            "Today is live",
            "Live today",
            f"Today’s World Cup games are open.\n\n{len(fixtures_today)} fixtures. {total_entries} fan calls in the game.\n\nPick the score. Guess the first goal. Play for your country.\n\n{base}",
            base,
            "Use today fixture list screenshot.",
            "today",
        ))
    else:
        date_label = format_kickoff(upcoming[0]["kickoff_utc"]) if upcoming else "soon"
        sections["live_today"].append(make_post(
            "Pre-tournament countdown",
            "Live today",
            f"The World Cup prediction room is warming up.\n\nFirst fixtures open {date_label}.\n\nPick a score, guess the first goal and get your country moving up the table before everyone else piles in.\n\n{base}",
            base,
            "Use hero screenshot.",
            "countdown",
        ))

    for f in next_active[:6]:
        match_url = f"{base}{url_for('match', fixture_id=f['id'])}"
        sections["live_today"].append(make_post(
            f"Open now: {fixture_label(f)}",
            "Live today",
            f"{flag_name(f['home_team'])} v {flag_name(f['away_team'])} is open.\n\n{f['entry_count']} fan calls already in.\n\nScore prediction + first-goal minute tie-breaker.\n\nBack your country here: {match_url}",
            match_url,
            f"Use screenshot of {fixture_label(f)} prediction screen.",
            "match open",
        ))

    # Yesterday recap
    finished_yesterday = [f for f in fixtures_yesterday if f["status"] == "finished"]
    if finished_yesterday:
        recap_lines = []
        for f in finished_yesterday[:4]:
            score = f"{f['home_team']} {f['home_score']}-{f['away_score']} {f['away_team']}" if f["home_score"] is not None else fixture_label(f)
            recap_lines.append(f"• {score}")
        sections["yesterday"].append(make_post(
            "Yesterday recap",
            "Yesterday",
            "Yesterday’s World Cup prediction recap:\n\n" + "\n".join(recap_lines) + f"\n\nToday’s games are open here: {base}",
            base,
            "Use results/leaderboard screenshot.",
            "yesterday",
        ))
    else:
        sections["yesterday"].append(make_post(
            "Yesterday style post for later",
            "Yesterday",
            f"Yesterday’s prediction room was chaos.\n\nClose score calls, wild first-goal shouts and the country table moving all day.\n\nToday we go again. Pick your score before kick-off: {base}",
            base,
            "Template for when tournament is live.",
            "template",
        ))
        if latest_entries:
            lines = []
            for e in latest_entries[:4]:
                lines.append(f"• {e['player_name']} called {e['home_team']} {e['pred_home_goals']}-{e['pred_away_goals']} {e['away_team']} — first goal {e['first_goal_minute']}’")
            sections["yesterday"].append(make_post(
                "Recent calls recap",
                "Yesterday",
                "Recent World Cup calls from the game:\n\n" + "\n".join(lines) + f"\n\nGet your own call in: {base}",
                base,
                "Use recent calls panel screenshot.",
                "recap",
            ))

    # Tomorrow preview
    preview_fixtures = fixtures_tomorrow or upcoming[:6]
    if preview_fixtures:
        lines = []
        for f in preview_fixtures[:6]:
            lines.append(f"• {flag_name(f['home_team'])} v {flag_name(f['away_team'])} — {format_kickoff(f['kickoff_utc'])}")
        sections["tomorrow"].append(make_post(
            "Tomorrow / next up",
            "Tomorrow",
            "Next up in the World Cup prediction game:\n\n" + "\n".join(lines) + f"\n\nGet your score calls in early: {base}",
            base,
            "Use fixture list screenshot.",
            "tomorrow",
        ))

    # We predict
    for f in (fixtures_today or upcoming[:8]):
        ph, pa, fg = deterministic_prediction(f["home_team"], f["away_team"])
        match_url = f"{base}{url_for('match', fixture_id=f['id'])}"
        sections["we_predict"].append(make_post(
            f"We predict: {fixture_label(f)}",
            "We predict",
            f"Our call for {flag_name(f['home_team'])} v {flag_name(f['away_team'])}:\n\n{f['home_team']} {ph}-{pa} {f['away_team']}\nFirst goal: {fg}’\n\nThink you know better? Make your World Cup call here: {match_url}",
            match_url,
            f"Use {fixture_label(f)} match card.",
            "we predict",
        ))

    # Country race content for broader world angle
    for idx, r in enumerate(country_rows[:12], start=1):
        sections["country_race"].append(make_post(
            f"Country push: {r['country']}",
            "Country race",
            f"{flag_name(r['country'])} fans are currently #{idx} in the Matchday Brain country race with {r['entries']} calls.\n\nCan they climb today?\n\nPick a score, guess the first goal and play for your country: {base}",
            base,
            f"Use {r['country']} row from country leaderboard.",
            "country",
        ))

    # Player mention content: manual, opt-in style posts based only on entered X handles.
    seen_handles = set()
    spotlight = []
    for e in mention_entries:
        handle = clean_x_handle(e["x_handle"])
        key = handle.lower()
        if not handle or key in seen_handles:
            continue
        seen_handles.add(key)
        spotlight.append(e)
        if len(spotlight) >= 8:
            break

    if spotlight:
        for e in spotlight[:6]:
            mention = x_mention(e["x_handle"])
            match_url = f"{base}{url_for('match', fixture_id=e['fixture_id'])}"
            sections["player_mentions"].append(make_post(
                f"Player spotlight: {mention}",
                "Player mentions",
                f"Player spotlight 🎯\n\n{mention} has called {flag_name(e['home_team'])} {e['pred_home_goals']}-{e['pred_away_goals']} {flag_name(e['away_team'])}.\nFirst goal: {e['first_goal_minute']}’\n\nThink they have nailed it? Make your call before kick-off: {match_url}",
                match_url,
                "Use this player's prediction/thanks screen or the match card.",
                "player mention",
            ))

        handles = [x_mention(e["x_handle"]) for e in spotlight[:3] if x_mention(e["x_handle"])]
        if handles:
            sections["player_mentions"].append(make_post(
                "Fresh callers to mention",
                "Player mentions",
                "Fresh Matchday Brain calls just landed:\n\n" + "\n".join([f"• {h}" for h in handles]) + f"\n\nWho is calling it right? Pick your score and first-goal minute: {base}",
                base,
                "Use recent calls panel screenshot.",
                "recent handles",
            ))

    # Per-match top mention posts, capped at 3 handles to keep posts clean.
    for f in fixtures[:24]:
        handles = conn.execute(
            """
            SELECT TRIM(x_handle) AS x_handle
            FROM entries
            WHERE fixture_id=? AND TRIM(COALESCE(x_handle, '')) <> ''
            ORDER BY created_at DESC
            LIMIT 3
            """,
            (f["id"],),
        ).fetchall()
        mentions = [x_mention(r["x_handle"]) for r in handles if x_mention(r["x_handle"])]
        if mentions:
            match_url = f"{base}{url_for('match', fixture_id=f['id'])}"
            sections["player_mentions"].append(make_post(
                f"Mention pack: {fixture_label(f)}",
                "Player mentions",
                f"Early callers for {flag_name(f['home_team'])} v {flag_name(f['away_team'])}:\n\n" + "\n".join([f"• {m}" for m in mentions[:3]]) + f"\n\nWant your call in the mix? Play here: {match_url}",
                match_url,
                f"Use screenshot of {fixture_label(f)} Fan Pulse / recent calls.",
                "mention pack",
            ))

    # Finished match mention posts: useful for reposts after results are entered.
    finished_with_handles = [e for e in mention_entries if str(e["status"]).lower() == "finished" and e["home_score"] is not None and e["away_score"] is not None]
    for e in finished_with_handles[:6]:
        mention = x_mention(e["x_handle"])
        scored = score_entry(e, e)
        points = scored["points"] if scored else 0
        match_url = f"{base}{url_for('match', fixture_id=e['fixture_id'])}"
        sections["player_mentions"].append(make_post(
            f"Result reaction: {mention}",
            "Player mentions",
            f"Result check ✅\n\n{mention} called {e['home_team']} {e['pred_home_goals']}-{e['pred_away_goals']} {e['away_team']}.\nActual: {e['home_team']} {e['home_score']}-{e['away_score']} {e['away_team']}.\nScore: {points} pts.\n\nLeaderboard: {base}/leaderboard",
            f"{base}/leaderboard",
            "Use leaderboard screenshot after result is logged.",
            "result mention",
        ))

    # Match angles from actual played data
    active_fixtures = sorted(fixtures, key=lambda f: f["entry_count"], reverse=True)[:12]
    for f in active_fixtures:
        if not f["entry_count"]:
            continue
        score_rows = conn.execute(
            """
            SELECT pred_home_goals, pred_away_goals, COUNT(*) AS entries
            FROM entries
            WHERE fixture_id=?
            GROUP BY pred_home_goals, pred_away_goals
            ORDER BY entries DESC, pred_home_goals DESC, pred_away_goals ASC
            LIMIT 3
            """,
            (f["id"],),
        ).fetchall()
        if score_rows:
            score_line = " / ".join([f"{r['pred_home_goals']}-{r['pred_away_goals']} ({r['entries']})" for r in score_rows])
            match_url = f"{base}{url_for('match', fixture_id=f['id'])}"
            sections["match_angles"].append(make_post(
                f"Most picked score: {fixture_label(f)}",
                "Match angles",
                f"Most picked score calls for {flag_name(f['home_team'])} v {flag_name(f['away_team'])}:\n\n{score_line}\n\nAre the fans right? Make your call before kick-off: {match_url}",
                match_url,
                "Use most picked score panel.",
                "popular score",
            ))
        backers = conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral') AS country, COUNT(*) AS entries
            FROM entries
            WHERE fixture_id=?
            GROUP BY COALESCE(NULLIF(TRIM(club_supporting), ''), 'Neutral')
            ORDER BY entries DESC
            LIMIT 2
            """,
            (f["id"],),
        ).fetchall()
        if len(backers) >= 2:
            match_url = f"{base}{url_for('match', fixture_id=f['id'])}"
            sections["match_angles"].append(make_post(
                f"Fan backing: {fixture_label(f)}",
                "Match angles",
                f"Fan backing for {flag_name(f['home_team'])} v {flag_name(f['away_team'])}:\n\n{flag_name(backers[0]['country'])}: {backers[0]['entries']} calls\n{flag_name(backers[1]['country'])}: {backers[1]['entries']} calls\n\nAdd your country to the race: {match_url}",
                match_url,
                "Use country selector / match card screenshot.",
                "fan backing",
            ))

    # Final hashtag pass: ensure every generated post has global tags and
    # add country tags where team/country names appear in the copy.
    known_teams = list(COUNTRY_X_HASHTAGS.keys())
    for items in sections.values():
        for post in items:
            matched = [team for team in known_teams if team and team in post.get("body", "")]
            post["body"] = add_x_hashtags(post.get("body", ""), *matched[:4])

    conn.close()
    return sections



def _font(size=44, bold=False):
    if ImageFont is None:
        return None
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    lines = []
    for paragraph in str(text or '').split('\n'):
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        line = ''
        for word in words:
            test = (line + ' ' + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width or not line:
                line = test
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
    return lines




def _team_colours(team):
    colours = {
        "Mexico": ((0, 104, 71), (206, 17, 38)),
        "South Africa": ((0, 119, 73), (222, 56, 49)),
        "South Korea": ((0, 71, 160), (205, 46, 58)),
        "Czech Republic": ((17, 69, 126), (214, 20, 32)),
        "England": ((255, 255, 255), (196, 18, 48)),
        "Croatia": ((23, 76, 154), (196, 18, 48)),
        "United States": ((60, 59, 110), (178, 34, 52)),
        "Paraguay": ((0, 56, 97), (213, 43, 30)),
        "Brazil": ((0, 156, 59), (255, 223, 0)),
        "Argentina": ((116, 172, 223), (255, 255, 255)),
        "France": ((0, 35, 149), (237, 41, 57)),
        "Germany": ((0, 0, 0), (255, 206, 0)),
        "Spain": ((198, 11, 30), (255, 196, 0)),
        "Portugal": ((0, 102, 0), (255, 0, 0)),
        "Netherlands": ((174, 28, 40), (33, 70, 139)),
        "Belgium": ((0, 0, 0), (253, 218, 36)),
        "Canada": ((255, 255, 255), (255, 0, 0)),
        "Scotland": ((0, 94, 184), (255, 255, 255)),
        "Japan": ((255, 255, 255), (188, 0, 45)),
        "Australia": ((0, 47, 108), (255, 205, 0)),
        "Morocco": ((193, 39, 45), (0, 98, 51)),
        "Ghana": ((239, 51, 64), (252, 209, 22)),
        "Uruguay": ((255, 255, 255), (0, 56, 168)),
        "Qatar": ((140, 24, 57), (255, 255, 255)),
        "Switzerland": ((218, 41, 28), (255, 255, 255)),
        "Turkey": ((227, 10, 23), (255, 255, 255)),
        "Sweden": ((0, 106, 167), (254, 204, 0)),
        "Tunisia": ((231, 0, 19), (255, 255, 255)),
        "Egypt": ((206, 17, 38), (0, 0, 0)),
        "New Zealand": ((0, 34, 68), (204, 20, 43)),
        "Saudi Arabia": ((0, 108, 53), (255, 255, 255)),
        "Senegal": ((0, 133, 63), (227, 27, 35)),
        "Norway": ((186, 12, 47), (0, 32, 91)),
        "Algeria": ((0, 98, 51), (255, 255, 255)),
        "Austria": ((237, 41, 57), (255, 255, 255)),
        "Colombia": ((252, 209, 22), (0, 56, 147)),
    }
    return colours.get(str(team or "").strip(), ((18, 73, 190), (255, 207, 74)))


def _font(size=44, bold=False):
    """Robust Railway-friendly font loader.

    If Railway has no system TTF fonts, the drawing helpers below scale the
    default PIL bitmap font so text is still large and readable.
    """
    if ImageFont is None:
        return None
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _font_is_tiny(font, size):
    try:
        box = font.getbbox("MATCHDAY BRAIN")
        return (box[3] - box[1]) < max(12, size * 0.45)
    except Exception:
        return True


def _draw_big_text(img, xy, text, size=48, fill=(255,255,255), bold=True, anchor=None, stroke=0, stroke_fill=(0,0,0)):
    """Draws readable text even when no TTF fonts are installed on Railway."""
    if Image is None:
        return
    draw = ImageDraw.Draw(img)
    font = _font(size, bold)
    text = str(text or "")
    if font is not None and not _font_is_tiny(font, size):
        draw.text(xy, text, fill=fill, font=font, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)
        return

    # Fallback: render PIL default font to a small transparent layer then scale.
    small_font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=small_font, stroke_width=stroke)
    tw, th = max(1, bbox[2]-bbox[0]), max(1, bbox[3]-bbox[1])
    target_h = size
    scale = max(2, int(round(target_h / max(8, th))))
    layer = Image.new("RGBA", (tw + 8 + stroke*4, th + 8 + stroke*4), (0,0,0,0))
    ld = ImageDraw.Draw(layer)
    ld.text((4 + stroke*2, 4 + stroke*2), text, fill=fill + (255,), font=small_font, stroke_width=stroke, stroke_fill=stroke_fill + (255,))
    layer = layer.resize((layer.width * scale, layer.height * scale), Image.Resampling.BICUBIC)
    x, y = xy
    if anchor == "mm":
        x -= layer.width // 2
        y -= layer.height // 2
    elif anchor == "mt":
        x -= layer.width // 2
    elif anchor == "rm":
        x -= layer.width
        y -= layer.height // 2
    img.alpha_composite(layer, (int(x), int(y)))


def _text_width(draw, text, size=48, bold=True):
    font = _font(size, bold)
    try:
        if font is not None and not _font_is_tiny(font, size):
            b = draw.textbbox((0,0), str(text), font=font)
            return b[2]-b[0]
    except Exception:
        pass
    # approximate fallback scaled default
    f = ImageFont.load_default()
    b = draw.textbbox((0,0), str(text), font=f)
    return int((b[2]-b[0]) * max(2, size/9))


def _fit_size(draw, text, max_width, start=56, minimum=26, bold=True):
    for size in range(start, minimum-1, -2):
        if _text_width(draw, text, size, bold) <= max_width:
            return size
    return minimum


def _draw_flag(draw, box, team):
    x1, y1, x2, y2 = [int(v) for v in box]
    w, h = x2-x1, y2-y1
    team = str(team or "")
    c1, c2 = _team_colours(team)

    draw.rounded_rectangle((x1-6, y1-6, x2+6, y2+6), radius=18, fill=(255, 207, 74))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=14, fill=(245, 247, 255))

    if team in ("Mexico", "France", "Belgium", "Italy", "Canada"):
        third = w // 3
        draw.rectangle((x1, y1, x1+third, y2), fill=c1)
        draw.rectangle((x1+third, y1, x1+2*third, y2), fill=(246,248,255))
        draw.rectangle((x1+2*third, y1, x2, y2), fill=c2)
        if team == "Mexico":
            draw.ellipse((x1+w//2-26, y1+h//2-26, x1+w//2+26, y1+h//2+26), fill=(145, 92, 42), outline=(0, 100, 60), width=4)
        if team == "Canada":
            draw.polygon([(x1+w//2, y1+h//2-32), (x1+w//2+15, y1+h//2), (x1+w//2, y1+h//2+32), (x1+w//2-15, y1+h//2)], fill=(255,0,0))
    elif team == "South Africa":
        draw.rectangle((x1, y1, x2, y1+h//2), fill=(222, 56, 49))
        draw.rectangle((x1, y1+h//2, x2, y2), fill=(0, 35, 149))
        draw.polygon([(x1, y1), (x1+int(w*.55), y1+h//2), (x1, y2)], fill=(0,119,73))
        draw.polygon([(x1, y1+12), (x1+int(w*.43), y1+h//2), (x1, y2-12)], fill=(255,184,28))
        draw.polygon([(x1, y1+30), (x1+int(w*.30), y1+h//2), (x1, y2-30)], fill=(0,0,0))
    elif team == "Czech Republic":
        draw.rectangle((x1, y1, x2, y1+h//2), fill=(255,255,255))
        draw.rectangle((x1, y1+h//2, x2, y2), fill=(214,20,32))
        draw.polygon([(x1, y1), (x1+int(w*.50), y1+h//2), (x1, y2)], fill=(17,69,126))
    elif team == "South Korea":
        draw.rectangle((x1, y1, x2, y2), fill=(255,255,255))
        draw.pieslice((x1+w//2-42, y1+h//2-42, x1+w//2+42, y1+h//2+42), 90, 270, fill=(205,46,58))
        draw.pieslice((x1+w//2-42, y1+h//2-42, x1+w//2+42, y1+h//2+42), 270, 90, fill=(0,71,160))
        for dx, dy in [(-82,-50),(64,-50),(-82,46),(64,46)]:
            draw.rectangle((x1+w//2+dx, y1+h//2+dy, x1+w//2+dx+46, y1+h//2+dy+8), fill=(0,0,0))
            draw.rectangle((x1+w//2+dx, y1+h//2+dy+17, x1+w//2+dx+46, y1+h//2+dy+25), fill=(0,0,0))
    elif team == "Brazil":
        draw.rectangle((x1, y1, x2, y2), fill=(0,156,59))
        draw.polygon([(x1+w//2,y1+16),(x2-28,y1+h//2),(x1+w//2,y2-16),(x1+28,y1+h//2)], fill=(255,223,0))
        draw.ellipse((x1+w//2-42,y1+h//2-42,x1+w//2+42,y1+h//2+42), fill=(0,39,118))
    elif team == "Argentina":
        draw.rectangle((x1, y1, x2, y1+h//3), fill=(116,172,223))
        draw.rectangle((x1, y1+h//3, x2, y1+2*h//3), fill=(255,255,255))
        draw.rectangle((x1, y1+2*h//3, x2, y2), fill=(116,172,223))
        draw.ellipse((x1+w//2-18,y1+h//2-18,x1+w//2+18,y1+h//2+18), fill=(255,207,74))
    elif team == "Germany":
        draw.rectangle((x1, y1, x2, y1+h//3), fill=(0,0,0))
        draw.rectangle((x1, y1+h//3, x2, y1+2*h//3), fill=(221,0,0))
        draw.rectangle((x1, y1+2*h//3, x2, y2), fill=(255,206,0))
    elif team == "Spain":
        draw.rectangle((x1, y1, x2, y1+h//4), fill=(198,11,30))
        draw.rectangle((x1, y1+h//4, x2, y1+3*h//4), fill=(255,196,0))
        draw.rectangle((x1, y1+3*h//4, x2, y2), fill=(198,11,30))
    elif team == "England":
        draw.rectangle((x1, y1, x2, y2), fill=(255,255,255))
        draw.rectangle((x1+w//2-14, y1, x1+w//2+14, y2), fill=(196,18,48))
        draw.rectangle((x1, y1+h//2-14, x2, y1+h//2+14), fill=(196,18,48))
    else:
        draw.rectangle((x1, y1, x2, y1+h//2), fill=c1)
        draw.rectangle((x1, y1+h//2, x2, y2), fill=c2)

    draw.rounded_rectangle((x1, y1, x2, y2), radius=14, outline=(255,238,170), width=2)


def generate_match_social_card(fixture, entries=0):
    """Generate a readable 1200x630 match-poster image for X/social previews."""
    if Image is None:
        return None

    W, H = 1200, 630
    home = str(fixture["home_team"])
    away = str(fixture["away_team"])
    kickoff = format_kickoff(fixture["kickoff_utc"]) if fixture.get("kickoff_utc") else "Kick-off TBC"

    img = Image.new("RGBA", (W, H), (3, 12, 34, 255))
    draw = ImageDraw.Draw(img)

    # Deep blue broadcast background
    for y in range(H):
        t = y / H
        draw.line((0, y, W, y), fill=(3, int(14 + 24*t), int(48 + 82*t), 255))

    c1, _ = _team_colours(home)
    c2, _ = _team_colours(away)
    glow = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-180, 70, 520, 650), fill=(c1[0], c1[1], c1[2], 95))
    gd.ellipse((690, 70, 1380, 650), fill=(c2[0], c2[1], c2[2], 95))
    gd.ellipse((390, 205, 810, 555), fill=(255, 207, 74, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(50))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    gold = (255, 207, 74)
    white = (255,255,255)
    navy = (4, 15, 44)

    # Floodlights / stadium feel
    for x in (85, 1115):
        for i in range(8):
            draw.ellipse((x-62+i*17, 30+(i%2)*5, x-51+i*17, 41+(i%2)*5), fill=(230,245,255,255))
        draw.line((x, 46, 600, 360), fill=(52, 145, 255, 120), width=2)
    draw.arc((-180, 405, 1380, 860), 200, 340, fill=(255,207,74,180), width=7)
    draw.arc((-90, 445, 1290, 820), 202, 338, fill=(42,158,255,140), width=3)

    # Confetti
    for i in range(95):
        x = (i * 149 + 37) % W
        y = (i * 71 + 19) % H
        col = (255,207,74,220) if i % 3 == 0 else (38,158,255,200)
        draw.rectangle((x, y, x+8, y+3), fill=col)

    # Brand header
    _draw_big_text(img, (600, 30), "MATCHDAY BRAIN", 46, white, True, anchor="mt", stroke=2, stroke_fill=(0,0,0))
    draw.rounded_rectangle((350, 102, 850, 150), radius=14, fill=(5,18,52,235), outline=gold, width=3)
    _draw_big_text(img, (600, 111), "WORLD CUP 2026 TEST RUN", 25, gold, True, anchor="mt")

    # Flags
    _draw_flag(draw, (92, 190, 462, 310), home)
    _draw_flag(draw, (738, 190, 1108, 310), away)

    # Name plates
    draw.rounded_rectangle((76, 316, 478, 382), radius=10, fill=(5,18,52,245), outline=gold, width=3)
    draw.rounded_rectangle((722, 316, 1124, 382), radius=10, fill=(5,18,52,245), outline=gold, width=3)
    hs = _fit_size(draw, home.upper(), 340, 42, 25, True)
    aw = _fit_size(draw, away.upper(), 340, 42, 25, True)
    _draw_big_text(img, (277, 330), home.upper(), hs, white, True, anchor="mt", stroke=1, stroke_fill=(0,0,0))
    _draw_big_text(img, (923, 330), away.upper(), aw, white, True, anchor="mt", stroke=1, stroke_fill=(0,0,0))

    # VS
    _draw_big_text(img, (600, 222), "VS", 92, gold, True, anchor="mt", stroke=3, stroke_fill=(0,0,0))
    draw.line((590, 200, 625, 352), fill=(255,238,170,210), width=3)

    # Details strip
    draw.rounded_rectangle((225, 405, 975, 462), radius=14, fill=(6,20,58,245), outline=gold, width=2)
    _draw_big_text(img, (280, 418), kickoff, 27, white, True)
    draw.line((615, 413, 615, 454), fill=(255,255,255,190), width=1)
    fan_text = f"{entries} FAN CALL{'S' if int(entries) != 1 else ''}"
    _draw_big_text(img, (675, 418), fan_text, 27, gold, True)

    # CTA
    _draw_big_text(img, (600, 487), "PREDICT THE SCORE.", 46, white, True, anchor="mt", stroke=2, stroke_fill=(0,0,0))
    _draw_big_text(img, (600, 535), "GUESS THE FIRST GOAL.", 48, gold, True, anchor="mt", stroke=2, stroke_fill=(0,0,0))
    draw.rounded_rectangle((145, 582, 1055, 624), radius=13, fill=(5,18,52,245), outline=gold, width=2)
    _draw_big_text(img, (600, 590), "BACK YOUR COUNTRY AT MATCHDAYBRAIN.COM", 27, white, True, anchor="mt")

    return img.convert("RGB")


def generate_social_card(title, subtitle='', kicker='MATCHDAY BRAIN', matchup=''):
    """Fallback home/admin card."""
    if Image is None:
        return None

    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), (3, 12, 34, 255))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line((0, y, W, y), fill=(3, int(14 + 24*t), int(48 + 82*t), 255))
    gold = (255, 207, 74)
    white = (255,255,255)
    muted = (205, 219, 248)

    draw.ellipse((740, 110, 1340, 710), fill=(12,62,170,190))
    draw.arc((-100, 410, 1360, 850), 198, 342, fill=gold, width=8)
    _draw_big_text(img, (80, 70), "MATCHDAY", 58, white, True)
    _draw_big_text(img, (432, 70), "BRAIN", 58, gold, True)
    _draw_big_text(img, (84, 136), "FOOTBALL PREDICTOR", 28, muted, True)

    y = 220
    for line in _wrap(draw, title, _font(58, True), 760)[:4]:
        _draw_big_text(img, (80, y), line, 58, white if "country" not in line.lower() else gold, True)
        y += 65
    y += 12
    for line in _wrap(draw, subtitle, _font(28, False), 720)[:4]:
        _draw_big_text(img, (82, y), line, 28, muted, False)
        y += 38

    draw.ellipse((820, 220, 1060, 460), fill=(8,22,60,230), outline=gold, width=7)
    draw.ellipse((885, 275, 995, 385), fill=gold)
    draw.rounded_rectangle((80, 540, 520, 595), radius=18, fill=gold)
    _draw_big_text(img, (118, 553), "PLAY NOW", 32, (5,18,52), True)
    return img.convert("RGB")


@app.route('/og/home.png')
def og_home_image():
    img = generate_social_card(
        'Pick the score. Guess the first goal. Play for your country.',
        'Free football prediction game for World Cup 2026 fans. Make your call before kick-off.',
        'MATCHDAY BRAIN',
        'World Cup 2026',
    )
    if img is None:
        abort(503)
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png', headers={'Cache-Control': 'public, max-age=300'})


@app.route('/og/match/<int:fixture_id>.png')
def og_match_image(fixture_id):
    conn = get_db()
    f = conn.execute('SELECT * FROM fixtures WHERE id=?', (fixture_id,)).fetchone()
    entries = conn.execute('SELECT COUNT(*) FROM entries WHERE fixture_id=?', (fixture_id,)).fetchone()[0] if f else 0
    conn.close()
    if not f:
        abort(404)
    title = f"{f['home_team']} v {f['away_team']}"
    subtitle = f"{entries} fan calls in. Pick your score and first-goal minute before kick-off."
    img = generate_match_social_card(f, entries)
    if img is None:
        abort(503)
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png', headers={'Cache-Control': 'public, max-age=300'})


@app.route('/admin/posts/<int:post_id>/image.png')
def admin_post_image(post_id):
    admin_required()
    conn = get_db()
    post = conn.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
    if not post:
        conn.close()
        abort(404)

    body = str(post['body'] or '')
    link_url = str(post['link_url'] or '')
    match = re.search(r'/match/(\d+)', body + ' ' + link_url)
    img = None
    if match:
        fixture_id = int(match.group(1))
        fixture = conn.execute('SELECT * FROM fixtures WHERE id=?', (fixture_id,)).fetchone()
        entries = conn.execute('SELECT COUNT(*) FROM entries WHERE fixture_id=?', (fixture_id,)).fetchone()[0] if fixture else 0
        if fixture:
            img = generate_match_social_card(fixture, entries)
    conn.close()

    if img is None:
        clean = ' '.join([part for part in body.replace('\n', ' ').split() if not part.startswith('http') and not part.startswith('#')])
        img = generate_social_card(post['title'], clean[:180], 'MATCHDAY BRAIN', 'X post image')
    if img is None:
        abort(503)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png', headers={'Content-Disposition': f'inline; filename=matchday-post-{post_id}.png'})


@app.route("/admin/posts", methods=["GET", "POST"])
def admin_posts():
    admin_required()
    conn = get_db()
    if request.method == "POST":
        post_id = request.form.get("post_id")
        status = request.form.get("status")
        if post_id and status in ("draft", "scheduled", "posted", "ignored"):
            posted_at = utc_now_iso() if status == "posted" else None
            conn.execute("UPDATE posts SET status=?, posted_at=COALESCE(?, posted_at) WHERE id=?", (status, posted_at, post_id))
            conn.commit()
            flash("Post status updated.", "ok")
        return redirect(url_for("admin_posts"))

    posts = conn.execute("SELECT * FROM posts ORDER BY datetime(COALESCE(scheduled_at, created_at)) DESC").fetchall()
    conn.close()
    return render_template("admin_posts.html", posts=posts)




@app.route("/admin/content")
def admin_content():
    admin_required()
    sections = build_content_engine()
    total = sum(len(items) for items in sections.values())
    return render_template("admin_content.html", sections=sections, total=total)


@app.route("/admin/content/save", methods=["POST"])
def admin_content_save():
    admin_required()
    title = request.form.get("title", "Suggested post").strip() or "Suggested post"
    body = request.form.get("body", "").strip()
    link_url = request.form.get("link_url", "").strip()
    image_note = request.form.get("image_note", "").strip()
    if not body:
        flash("No post text to save.", "error")
        return redirect(url_for("admin_content"))
    conn = get_db()
    conn.execute(
        """
        INSERT INTO posts (title, body, scheduled_at, status, link_url, image_note, created_at)
        VALUES (?, ?, '', 'draft', ?, ?, ?)
        """,
        (title, body, link_url, image_note, utc_now_iso()),
    )
    conn.commit()
    conn.close()
    flash("Post saved to the planner.", "ok")
    return redirect(url_for("admin_content"))


@app.route("/admin/posts/new", methods=["GET", "POST"])
def admin_post_new():
    admin_required()
    conn = get_db()
    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO posts (title, body, scheduled_at, status, link_url, image_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.form.get("title", "").strip() or "Untitled post",
                request.form.get("body", "").strip(),
                request.form.get("scheduled_at", "").strip(),
                request.form.get("status", "draft"),
                request.form.get("link_url", "").strip(),
                request.form.get("image_note", "").strip(),
                utc_now_iso(),
            ),
        )
        conn.commit()
        conn.close()
        flash("Post created.", "ok")
        return redirect(url_for("admin_posts"))
    conn.close()
    return render_template("admin_post_form.html")


@app.route("/admin/posts/suggest")
def admin_post_suggest():
    admin_required()
    conn = get_db()
    fixture = conn.execute(
        """
        SELECT f.*, COUNT(e.id) AS entries
        FROM fixtures f
        LEFT JOIN entries e ON e.fixture_id=f.id
        GROUP BY f.id
        ORDER BY entries DESC, datetime(f.kickoff_utc) ASC
        LIMIT 1
        """
    ).fetchone()
    if not fixture:
        conn.close()
        flash("Load World Cup fixtures first.", "error")
        return redirect(url_for("admin_posts"))

    body = (
        f"World Cup buzz is building. {team_flag(fixture['home_team'])} {fixture['home_team']} v "
        f"{team_flag(fixture['away_team'])} {fixture['away_team']} is open now.\n\n"
        f"Pick your score and first-goal minute tie-breaker before kick-off.\n\n"
        f"Play here: {public_base_url()}{url_for('match', fixture_id=fixture['id'])}"
    )
    body = add_x_hashtags(body, fixture["home_team"], fixture["away_team"])
    conn.execute(
        """
        INSERT INTO posts (title, body, scheduled_at, status, link_url, image_note, created_at)
        VALUES (?, ?, ?, 'draft', ?, ?, ?)
        """,
        (
            f"Promo: {fixture['home_team']} v {fixture['away_team']}",
            body,
            "",
            f"{public_base_url()}{url_for('match', fixture_id=fixture['id'])}",
            "Use a phone screenshot of the World Cup prediction page.",
            utc_now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    flash("Suggested X post created.", "ok")
    return redirect(url_for("admin_posts"))


def seed_demo_data(clear=True):
    """Load the 2026 World Cup group stage plus believable demo entries."""
    init_db()
    conn = get_db()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    if clear:
        conn.execute("DELETE FROM posts")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM fixtures")
        conn.execute("DELETE FROM clubs")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('posts','entries','fixtures','clubs')")

    for group_name, teams in GROUPS.items():
        for team in teams:
            slug = slugify(team)
            conn.execute(
                """
                INSERT INTO clubs (name, short_name, slug, league_name, logo_filename, primary_color, secondary_color, active, created_at)
                VALUES (?, ?, ?, ?, ?, '#111827', '#facc15', 1, ?)
                ON CONFLICT(name) DO UPDATE SET
                    short_name=excluded.short_name,
                    league_name=excluded.league_name,
                    logo_filename=excluded.logo_filename,
                    active=1
                """,
                (team, team_code(team), slug, group_name, logo_for_team(team), utc_now_iso()),
            )

    for idx, (group_name, home, away, kickoff_uk, venue) in enumerate(WORLD_CUP_FIXTURES_UK, start=1):
        home_slug = ensure_club(conn, home, group_name)
        away_slug = ensure_club(conn, away, group_name)
        external_id = f"wc2026-gs-{idx:02d}"
        conn.execute(
            """
            INSERT INTO fixtures (
                external_id, league_id, league_name, home_team, away_team, home_slug, away_slug,
                kickoff_utc, status, home_score, away_score, actual_first_goal_minute, venue, source, updated_at
            ) VALUES (?, 'wc2026', ?, ?, ?, ?, ?, ?, 'scheduled', NULL, NULL, NULL, ?, 'worldcup_demo', ?)
            ON CONFLICT(external_id) DO UPDATE SET
                league_id=excluded.league_id,
                league_name=excluded.league_name,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                home_slug=excluded.home_slug,
                away_slug=excluded.away_slug,
                kickoff_utc=excluded.kickoff_utc,
                status=excluded.status,
                home_score=excluded.home_score,
                away_score=excluded.away_score,
                actual_first_goal_minute=excluded.actual_first_goal_minute,
                venue=excluded.venue,
                updated_at=excluded.updated_at
            """,
            (external_id, group_name, home, away, home_slug, away_slug, uk_to_utc_iso(kickoff_uk), venue, utc_now_iso()),
        )

    rnd = random.Random(2026)
    # Put heavier activity around home nations and glamour fixtures so the app feels alive.
    fixtures = conn.execute("SELECT * FROM fixtures ORDER BY id").fetchall()
    glamour = {"England", "Scotland", "Brazil", "Argentina", "France", "Spain", "Germany", "Portugal", "United States", "Mexico"}
    for fixture in fixtures:
        home = fixture["home_team"]
        away = fixture["away_team"]
        base = rnd.randint(8, 18)
        if home in glamour or away in glamour:
            base += rnd.randint(8, 16)
        for i in range(base):
            player, handle, support, pub = rnd.choice(DEMO_PLAYERS)
            suffix = "" if i < 9 else f" {i+1}"
            pred_home = max(0, min(5, int(round(rnd.triangular(0, 5, 2)))))
            pred_away = max(0, min(5, int(round(rnd.triangular(0, 5, 1)))))
            if rnd.random() < 0.45:
                support = rnd.choice([home, away, support])
            created = (now - timedelta(minutes=rnd.randint(2, 3600))).isoformat()
            conn.execute(
                """
                INSERT INTO entries (
                    fixture_id, player_name, x_handle, email, club_supporting, pub_group,
                    pred_home_goals, pred_away_goals, first_goal_minute, attendance_guess,
                    mood, ip_hash, created_at
                ) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    fixture["id"], f"{player}{suffix}", handle, support, "",
                    pred_home, pred_away, rnd.randint(1, 89),
                    rnd.choice(MOODS), hashlib.sha256(f"wc-demo-{fixture['id']}-{i}".encode()).hexdigest()[:20], created
                ),
            )

    posts = [
        (
            "World Cup test launch",
            "The World Cup prediction game is live for testing. Pick a score, choose the first-goal minute tie-breaker and back your country before kick-off.\n\nFree to play. Built for matchday buzz.",
            "2026-06-11 09:30",
            "scheduled",
            "Use a phone screenshot of the fixture cards with flags.",
        ),
        (
            "England opener push",
            "England v Croatia is open. Score prediction + first-goal minute tie-breaker.\n\nBack your country, get your mates involved and climb the leaderboard before kick-off.",
            "2026-06-17 12:30",
            "draft",
            "Use England/Croatia match card.",
        ),
        (
            "Country table angle",
            "Watching the World Cup with mates? Pick your country, call the score and see which nation has the loudest backing.\n\nPick your match, make your call, share it on X.",
            "2026-06-13 11:00",
            "draft",
            "Use country leaderboard screenshot.",
        ),
        (
            "Scotland fixture",
            "Scotland are back on the World Cup stage. Pick the score and first goal minute before kick-off.\n\nBack your country and get on the leaderboard.",
            "2026-06-14 09:00",
            "draft",
            "Use Scotland match card.",
        ),
    ]
    for title, body, scheduled_at, status, image_note in posts:
        conn.execute(
            """
            INSERT INTO posts (title, body, scheduled_at, status, link_url, image_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, scheduled_at, status, public_base_url() if has_request_context() else "", image_note, utc_now_iso()),
        )

    conn.commit()
    stats = {
        "clubs": conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
        "fixtures": conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0],
        "entries": conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
        "posts": conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
    }
    conn.close()
    return stats


@app.route("/admin/schedule/load", methods=["POST"])
def admin_load_schedule():
    admin_required()
    stats = seed_worldcup_schedule(clear=True)
    flash(f"Live schedule loaded: {stats['fixtures']} fixtures, {stats['clubs']} countries, {stats['entries']} entries and {stats['posts']} posts.", "ok")
    return redirect(url_for("admin_home"))


@app.route("/admin/demo/seed", methods=["POST"])
def admin_seed_demo():
    admin_required()
    stats = seed_demo_data(clear=True)
    flash(
        f"World Cup demo loaded: {stats['fixtures']} fixtures, {stats['entries']} entries, {stats['clubs']} countries and {stats['posts']} posts.",
        "ok",
    )
    return redirect(url_for("admin_home"))


@app.route("/admin/demo/clear", methods=["POST"])
def admin_clear_demo():
    admin_required()
    conn = get_db()
    conn.execute("DELETE FROM posts")
    conn.execute("DELETE FROM entries")
    conn.execute("DELETE FROM fixtures")
    conn.execute("DELETE FROM clubs")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('posts','entries','fixtures','clubs')")
    conn.commit()
    conn.close()
    flash("World Cup demo data cleared.", "ok")
    return redirect(url_for("admin_home"))


@app.route("/admin/export/entries.csv")
def admin_export_entries():
    admin_required()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT e.id, e.created_at, e.player_name, e.x_handle, e.email, e.club_supporting,
               f.home_team, f.away_team, f.kickoff_utc,
               e.pred_home_goals, e.pred_away_goals, e.first_goal_minute, e.mood,
               f.status, f.home_score, f.away_score, f.actual_first_goal_minute
        FROM entries e
        JOIN fixtures f ON f.id=e.fixture_id
        ORDER BY e.created_at DESC
        """
    ).fetchall()
    conn.close()
    output = io.StringIO()
    fields = [
        "id", "created_at", "player_name", "x_handle", "email", "club_supporting",
        "home_team", "away_team", "kickoff_utc", "pred_home_goals", "pred_away_goals",
        "first_goal_minute", "mood", "status", "home_score", "away_score", "actual_first_goal_minute"
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=matchday-brain-entries.csv"},
    )


@app.route("/health")
def health():
    return {"ok": True, "time": utc_now_iso()}


def guess_lan_ip():
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "YOUR-PC-IP"


# Initialise tables on import too, so Gunicorn/Railway starts with a ready database.
try:
    init_db()
    if os.getenv("AUTO_SEED_FIXTURES", "1") == "1":
        conn = get_db()
        fixture_count = conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0]
        conn.close()
        if fixture_count == 0:
            seed_worldcup_schedule(clear=False)
except Exception as exc:
    print(f"Matchday Brain startup database warning: {exc}")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5055"))
    lan_ip = guess_lan_ip()
    print("\n" + "=" * 62)
    print("Matchday Brain World Cup is starting")
    print(f"PC link:    http://127.0.0.1:{port}")
    print(f"Phone link: http://{lan_ip}:{port}  (same Wi-Fi/network)")
    print("If your phone cannot load it, allow TCP port 5055 in Windows Firewall.")
    print("=" * 62 + "\n")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "1") == "1")
