{\rtf1\ansi\ansicpg1252\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os\
import requests\
from flask import Flask, request, jsonify\
import gspread\
from google.oauth2.service_account import Credentials\
import json\
\
app = Flask(__name__)\
\
# Google Sheets Configuration\
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets']\
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vMFWGh1LOw68yeDw-Qtd1Odi7QW1DDS27D_SGAWeXak"\
\
def get_sheets_connection():\
    """Get Google Sheets connection using Railway secrets"""\
    # Get service account JSON from Railway environment variable\
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')\
    if not service_account_json:\
        raise Exception("GOOGLE_SERVICE_ACCOUNT environment variable not set")\
    \
    service_account_info = json.loads(service_account_json)\
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPE)\
    client = gspread.authorize(creds)\
    return client.open_by_url(SHEET_URL).worksheet('AllLeads')\
\
def normalize_phone(phone):\
    """Normalize phone number for comparison"""\
    digits_only = ''.join(filter(str.isdigit, str(phone)))\
    if len(digits_only) == 11 and digits_only.startswith('1'):\
        return digits_only[1:]\
    elif len(digits_only) == 10:\
        return digits_only\
    return digits_only\
\
def handle_unsubscribe(phone_number, message_text):\
    """Handle unsubscribe detection and sheet update"""\
    try:\
        # Fuzzy matching for unsubscribe keywords\
        unsubscribe_keywords = ["unsubscribe", "stop", "quit", "cancel", "opt out"]\
        message_lower = message_text.lower().strip()\
        \
        # Check if message contains unsubscribe keyword\
        is_unsubscribe = any(keyword in message_lower for keyword in unsubscribe_keywords)\
        \
        if is_unsubscribe:\
            print(f"\uc0\u55357 \u57003  Unsubscribe detected from \{phone_number\}: \{message_text\}")\
            \
            # Get AllLeads sheet\
            sheet = get_sheets_connection()\
            all_data = sheet.get_all_values()\
            \
            # Find lead by phone number\
            lead_found = False\
            for row_idx, row in enumerate(all_data, start=2):\
                if len(row) > 2:\
                    phone_in_row = row[2].strip() if row[2] else ""  # Column C\
                    \
                    if normalize_phone(phone_in_row) == normalize_phone(phone_number):\
                        # Update Column Q to "Not able to fund"\
                        sheet.update_acell(f'Q\{row_idx\}', "Not able to fund")\
                        print(f"\uc0\u9989  Updated AllLeads row \{row_idx\} for \{phone_number\}")\
                        lead_found = True\
                        break\
            \
            if not lead_found:\
                print(f"\uc0\u9888 \u65039  Phone \{phone_number\} not found in AllLeads")\
                \
    except Exception as e:\
        print(f"\uc0\u10060  Error processing unsubscribe: \{e\}")\
\
@app.route('/webhook', methods=['POST'])\
def webhook():\
    """Handle incoming Kixie webhook"""\
    try:\
        data = request.get_json()\
        \
        # Extract webhook data\
        phone_number = data.get('phone', '')\
        message_text = data.get('message', '')\
        \
        if phone_number and message_text:\
            handle_unsubscribe(phone_number, message_text)\
            \
        return jsonify(\{"status": "success"\}), 200\
        \
    except Exception as e:\
        print(f"\uc0\u10060  Webhook error: \{e\}")\
        return jsonify(\{"status": "error", "message": str(e)\}), 500\
\
@app.route('/health', methods=['GET'])\
def health_check():\
    """Health check endpoint"""\
    return jsonify(\{"status": "healthy"\}), 200\
\
if __name__ == '__main__':\
    port = int(os.environ.get('PORT', 5000))\
    app.run(host='0.0.0.0', port=port)}