from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# Clio API credentials 
CLIENT_ID = os.environ.get("CLIO_CLIENT_ID", "QqAqrSWKBubre7WFcAoqoUmAv4qODQWBtgc0wr6U")
CLIENT_SECRET = os.environ.get("CLIO_CLIENT_SECRET", "xeRvTCO2oiWrbUaYf4J0vTC6Sd8wkYO04fBR85Eo")
REFRESH_TOKEN = os.environ.get("CLIO_REFRESH_TOKEN", "ZXbPestqTIiI0oVoc4TTxghmvhCynB3OQmeSy0of")

def get_clio_access_token():
    token_url = "https://app.clio.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    print(f"Failed to refresh token: {response.text}", flush=True)
    return None

@app.route('/', methods=['GET', 'POST'])
def handle_webhook():
    if request.method == 'GET':
        return "Clio Webhook Endpoint Active", 200

    payload = request.get_json(silent=True)
    print(f"WEBHOOK RECEIVED: {payload}", flush=True)

    if not payload:
        return jsonify({"status": "no payload"}), 200

    try:
        data_field = payload.get("data", {})
        matter_id = data_field.get("id")
        
        if matter_id:
            print(f"Fetching details for matter ID: {matter_id}", flush=True)
            access_token = get_clio_access_token()
            
            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                # Fetch full matter details including custom fields
                matter_url = f"https://app.clio.com/api/v4/matters/{matter_id}.json?fields=id,display_number,custom_field_values"
                matter_res = requests.get(matter_url, headers=headers)
                
                if matter_res.status_code == 200:
                    matter_data = matter_res.json().get("data", {})
                    print(f"Matter Data Fetched: {matter_data}", flush=True)
                    
                    # Process custom fields and calculate balances
                    custom_fields = matter_data.get("custom_field_values", [])
                    for field in custom_fields:
                        print(f"Field: {field}", flush=True)
                        # Balance calculation logic hooks here
                        
                else:
                    print(f"Failed to fetch matter: {matter_res.text}", flush=True)
                    
    except Exception as e:
        print(f"Error processing webhook payload: {e}", flush=True)

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
