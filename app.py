from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# Clio API credentials 
CLIENT_ID = os.environ.get("CLIO_CLIENT_ID", "QqAqrSWKBubre7WFcAoqoUmAv4qODQWBtgc0wr6U")
CLIENT_SECRET = os.environ.get("CLIO_CLIENT_SECRET", "xeRvTCO2oiWrbUaYf4J0vTC6Sd8wkYO04fBR85Eo")
REFRESH_TOKEN = os.environ.get("CLIO_REFRESH_TOKEN", "ZXbPestqTIiI0oVoc4TTxghmvhCynB3OQmeSy0of")

# Hardcoded Custom Field Definition IDs
PRINCIPAL_BALANCE_ID = "22619285"
PUBLICATION_COSTS_ID = "23054810"
TOTAL_LEGAL_FEES_ID = "23054825"
TOTAL_PAST_DUE_ID = "22808180"

def get_clio_access_token():
    global REFRESH_TOKEN
    token_url = "https://app.clio.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        new_refresh_token = token_data.get("refresh_token")
        if new_refresh_token and new_refresh_token != REFRESH_TOKEN:
            REFRESH_TOKEN = new_refresh_token
            print(f"ROTATED REFRESH TOKEN: {REFRESH_TOKEN}", flush=True)
            
        return access_token
        
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
                
                # Fetch matter data including the nested custom field definition ID
                matter_url = f"https://app.clio.com/api/v4/matters/{matter_id}.json?fields=id,display_number,custom_field_values{{id,value,custom_field{{id}}}}"
                matter_res = requests.get(matter_url, headers=headers)
                
                if matter_res.status_code == 200:
                    matter_data = matter_res.json().get("data", {})
                    print(f"Matter Data Fetched: {matter_data}", flush=True)
                    
                    custom_fields = matter_data.get("custom_field_values", [])
                    
                    principal_balance = 0.0
                    publication_costs = 0.0
                    
                    for field in custom_fields:
                        custom_field_meta = field.get("custom_field", {})
                        field_def_id = str(custom_field_meta.get("id"))
                        field_value = field.get("value")
                        
                        print(f"Field Def ID: {field_def_id} | Value: {field_value}", flush=True)
                        
                        if field_def_id == PRINCIPAL_BALANCE_ID:
                            try:
                                principal_balance = float(field_value) if field_value else 0.0
                            except ValueError:
                                principal_balance = 0.0
                        elif field_def_id == PUBLICATION_COSTS_ID:
                            try:
                                publication_costs = float(field_value) if field_value else 0.0
                            except ValueError:
                                publication_costs = 0.0

                    calculated_total = principal_balance + publication_costs
                    print(f"Calculated Total Balance: {calculated_total}", flush=True)
                    
                    # Clio API requires the 'data' root wrapper for PATCH request bodies
                    updates = [
                        {"id": TOTAL_LEGAL_FEES_ID, "value": str(calculated_total)},
                        {"id": TOTAL_PAST_DUE_ID, "value": str(calculated_total)}
                    ]
                        
                    if updates:
                        patch_url = f"https://app.clio.com/api/v4/matters/{matter_id}.json"
                        patch_payload = {
                            "data": {
                                "custom_field_values": updates
                            }
                        }
                        patch_res = requests.patch(patch_url, json=patch_payload, headers=headers)
                        if patch_res.status_code == 200:
                            print(f"Successfully updated custom fields for matter {matter_id}", flush=True)
                        else:
                            print(f"Failed to update custom fields: {patch_res.text}", flush=True)
                else:
                    print(f"Failed to fetch matter: {matter_res.text}", flush=True)
                    
    except Exception as e:
        print(f"Error processing webhook payload: {e}", flush=True)

    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
