"""One-time local helper to obtain a YouTube OAuth refresh token.

Keep your downloaded Google OAuth client JSON local. Never commit it to GitHub.
Usage:
  pip install google-auth-oauthlib
  python youtube_oauth.py client_secret.json
"""
import json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

if len(sys.argv) != 2:
    raise SystemExit("Usage: python youtube_oauth.py client_secret.json")

with open(sys.argv[1], "r", encoding="utf-8") as f:
    config = json.load(f)

flow = InstalledAppFlow.from_client_config(config, SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\nYOUTUBE_REFRESH_TOKEN=")
print(creds.refresh_token)
print("\nAdd this value to GitHub Secret: YOUTUBE_REFRESH_TOKEN")
