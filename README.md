# Matchday Brain World Cup

A mobile-first World Cup prediction game: pick the score, guess the first goal minute, and play for your country.

## Start on Windows

Double-click:

```text
start_matchday.bat
```

Or run manually:

```bat
cd /d C:\apps\matchday-brain
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open on the PC:

```text
http://127.0.0.1:5055
```

## View on your phone

Your phone must be on the same Wi-Fi/network as the PC.

When the app starts it prints a phone link such as:

```text
http://192.168.1.54:5055
```

Open that on your phone. Do not use `127.0.0.1` on your phone because that means the phone itself, not your PC.

If the phone cannot connect, run `allow_firewall_5055.ps1` as Administrator or run:

```powershell
New-NetFirewallRule -DisplayName "Matchday Brain Flask 5055" -Direction Inbound -Protocol TCP -LocalPort 5055 -Action Allow
```

## Admin

```text
http://127.0.0.1:5055/admin
```

Default password is in `.env`:

```text
ADMIN_PASSWORD=change-this-password
```

## Mobile-first update
This build changes the match page order on phone screens so the flow is:
1. World Cup hook
2. Match card
3. Prediction form
4. Fan pulse

The desktop view remains a wider event dashboard layout, while phones get the actual game flow immediately without needing to scroll past all the desktop content.
