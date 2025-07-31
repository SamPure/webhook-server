import os
import requests
from flask import Flask, request, jsonify
import gspread
from google.oauth2.service_account import Credentials
import json
from difflib import SequenceMatcher

app = Flask(__name__)

# Google Sheets Configuration
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets']
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vMFWGh1LOw68yeDw-Qtd1Odi7QW1DDS27D_SGAWeXak"

def get_sheets_connection():
    """Get Google Sheets connection using Railway secrets"""
    # Get service account JSON from Railway environment variable
    service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
    if not service_account_json:
        raise Exception("GOOGLE_SERVICE_ACCOUNT environment variable not set")
    
    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open_by_url(SHEET_URL).worksheet('AllLeads')

def normalize_phone(phone):
    """Normalize phone number for comparison"""
    digits_only = ''.join(filter(str.isdigit, str(phone)))
    if len(digits_only) == 11 and digits_only.startswith('1'):
        return digits_only[1:]
    elif len(digits_only) == 10:
        return digits_only
    return digits_only

def fuzzy_match(text, keywords, threshold=0.8):
    """Fuzzy match text against keywords (case insensitive)"""
    text_lower = text.lower().strip()
    
    for keyword in keywords:
        # Exact match (case insensitive)
        if keyword.lower() in text_lower:
            return True
        
        # Fuzzy match using SequenceMatcher
        similarity = SequenceMatcher(None, text_lower, keyword.lower()).ratio()
        if similarity >= threshold:
            return True
    
    return False

def handle_unsubscribe(phone_number, message_text):
    """Handle unsubscribe detection and sheet update"""
    try:
        # Only "unsubscribe" and "stop" keywords with fuzzy matching
        unsubscribe_keywords = ["unsubscribe", "stop"]
        
        # Check if message contains unsubscribe keyword (fuzzy + case insensitive)
        is_unsubscribe = fuzzy_match(message_text, unsubscribe_keywords)
        
        if is_unsubscribe:
            print(f"🚫 Unsubscribe detected from {phone_number}: {message_text}")
            
            # Get AllLeads sheet
            sheet = get_sheets_connection()
            all_data = sheet.get_all_values()
            
            # Find lead by phone number in Column D (index 3)
            lead_found = False
            for row_idx, row in enumerate(all_data):
                if len(row) > 3:
                    phone_in_row = row[3].strip() if row[3] else ""  # Column D (index 3)
                    
                    if normalize_phone(phone_in_row) == normalize_phone(phone_number):
                        # Update Column Q to "Not able to fund"
                        # Add 1 to row_idx because sheets are 1-indexed
                        actual_row = row_idx + 1
                        sheet.update_acell(f'Q{actual_row}', "Not able to fund")
                        print(f"✅ Updated AllLeads row {actual_row} for {phone_number}")
                        lead_found = True
                        break
            
            if not lead_found:
                print(f"⚠️ Phone {phone_number} not found in AllLeads Column D")
                
    except Exception as e:
        print(f"❌ Error processing unsubscribe: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Kixie webhook"""
    try:
        data = request.get_json()
        
        # ADD DEBUG LOGGING
        print(f"🔔 Webhook received: {data}")
        
        # Extract webhook data from Kixie format
        if 'data' in data:
            kixie_data = data['data']
            direction = kixie_data.get('direction', '')
            
            # ONLY PROCESS INCOMING MESSAGES
            if direction == 'incoming':
                phone_number = kixie_data.get('from', '')  # Use 'from' for incoming messages
                message_text = kixie_data.get('message', '')
                
                print(f"📱 Phone: {phone_number}")
                print(f"💬 Message: {message_text}")
                print(f"📡 Direction: {direction}")
                
                if phone_number and message_text:
                    handle_unsubscribe(phone_number, message_text)
                else:
                    print(f"⚠️ Missing phone or message: phone={phone_number}, message={message_text}")
            else:
                print(f"⏭️ Skipping outgoing message (direction: {direction})")
        else:
            print("⚠️ No 'data' field in webhook payload")
            
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
