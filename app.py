import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Clio API Credentials
CLIENT_ID = os.environ.get("CLIO_CLIENT_ID", "QqAqrSWKBubre7WFcAoqoUmAv4qODQWBtgc0wr6U")
CLIENT_SECRET = os.environ.get("CLIO_CLIENT_SECRET", "xeRvTCO2oiWrbUaYf4J0vTC6Sd8wkYO04fBR85Eo")
REFRESH_TOKEN = os.environ.get("CLIO_REFRESH_TOKEN", "ZXbPestqTIiI0oVoc4TTxghmvhCynB3OQmeSy0of")

def get_access_token():
    """Refreshes and returns a valid Clio access token using the refresh token."""
    url = "https://app.clio.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Failed to refresh token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception occurred while refreshing token: {e}")
        return None

def calculate_balances(custom_fields):
    """
    Calculates Total Legal Fees & Expenses and Total Past Due using the specific custom fields:
    - Principal Balance
    - Interest
    - Total Payments
    - Publication Costs
    - Total Legal Fees & Expenses
    - Total Past Due
    """
    fields_dict = {}
    for field in custom_fields:
        name = field.get("name", "").strip()
        try:
            value = float(field.get("value") or 0.0)
        except (ValueError, TypeError):
            value = 0.0
        fields_dict[name] = value

    # Extract individual components (adjust exact text matching if needed)
    principal_balance = fields_dict.get("Principal Balance", 0.0)
    interest = fields_dict.get("Interest", 0.0)
    total_payments = fields_dict.get("Total Payments", 0.0)
    publication_costs = fields_dict.get("Publication Costs", 0.0)
    
    # Assuming billable activities can be tracked or parsed from custom fields if stored there, 
    # or defaulting to 0 if calculated via native Clio time entries.
    billable_activities = fields_dict.get("Billable Activities", 0.0)

    # Formula execution
    total_legal_fees_and_expenses = billable_activities + publication_costs
    total_past_due = total_legal_fees_and_expenses + principal_balance + interest - total_payments

    return {
        "Total Legal Fees & Expenses": total_legal_fees_and_expenses,
        "Total Past Due": total_past_due
    }

@app.route('/', methods=['POST'])
def handle_webhook():
    # 1. Handle Clio's webhook handshake verification header
    hook_secret = request.headers.get('X-Hook-Secret')
    if hook_secret:
        print("Responding to Clio webhook handshake verification.")
        return '', 200, {'X-Hook-Secret': hook_secret}
    
    # 2. Parse the incoming webhook payload safely
    payload = request.json
    print("Received webhook payload:", payload)
    
    if not payload or "data" not in payload:
        return jsonify({"status": "ignored", "reason": "no data field"}), 200
        
    event_data = payload["data"]
    matter_id = event_data.get("id")
    
    if not matter_id:
        print("Webhook payload did not contain a matter ID.")
        return jsonify({"status": "ignored", "reason": "no matter id found"}), 200

    print(f"Processing update for Matter ID: {matter_id}")

    # 3. Authenticate with Clio API
    access_token = get_access_token()
    if not access_token:
        print("Error: Could not obtain a valid Clio access token.")
        return jsonify({"error": "Failed to authenticate with Clio"}), 500

    # 4. Fetch full matter details including custom fields
    headers = {"Authorization": f"Bearer {access_token}"}
    matter_url = f"https://app.clio.com/api/v4/matters/{matter_id}.json?expand=custom_field_values"
    
    try:
        matter_response = requests.get(matter_url, headers=headers)
        if matter_response.status_code == 200:
            matter_data = matter_response.json().get("data", {})
            print(f"Successfully fetched matter details for ID {matter_id}.")
            
            custom_fields = matter_data.get("custom_field_values", [])
            
            # 5. Run the calculations
            results = calculate_balances(custom_fields)
            print(f"Calculation Results for Matter {matter_id}: {results}")
            
        else:
            print(f"Failed to fetch matter details: {matter_response.status_code} - {matter_response.text}")
    except Exception as e:
        print(f"Exception occurred while processing matter: {e}")

    return jsonify({"status": "success"}), 200

@app.route('/', methods=['GET'])
def health_check():
    return "Clio Webhook Server is running!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
