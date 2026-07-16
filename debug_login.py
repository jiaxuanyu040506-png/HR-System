import tomllib
import json
import gspread
from google.oauth2.service_account import Credentials
import bcrypt

with open('.streamlit/secrets.toml', 'rb') as f:
    secrets = tomllib.load(f)

creds = Credentials.from_service_account_info(
    secrets['gcp_service_account'],
    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.readonly'],
)
client = gspread.authorize(creds)
ws = client.open('HR_System_Database').worksheet('Employees')
rows = ws.get_all_records()
print('row_count=', len(rows))
for row in rows:
    print(row)
    print('---')
