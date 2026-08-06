import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

CLIENT_ID = "QqAqrSWKBubre7WFcAoqoUmAv4qODQWBtgc0wr6U"
CLIENT_SECRET = "xeRvTCO2oiWrbUaYf4J0vTC6Sd8wkYO04fBR85Eo"

def get_access_token():
    refresh_token = os.getenv("CLIO_REFRESH_TOKEN")
    response = requests.post("https://app.clio.com/oauth/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    return response.json().get("access_token")

@app.route("/", methods=["POST"])
def webhook():
    event_data = request.json
    print("Received webhook event:", event_data)
    
    # Extract matter ID from the incoming webhook payload
    try:
        model = event_data.get("data", {}).get("model", "")
        matter_id = event_data.get("data", {}).get("matter", {}).get("id") or event_data.get("data", {}).get("id")
        
        if not matter_id:
            return jsonify({"status": "ignored, no matter id found"}), 200
    except Exception as e:
        print(f"Error parsing webhook payload: {e}")
        return jsonify({"error": "Invalid payload"}, 400)

    access_token = get_access_token()
    if not access_token:
        return jsonify({"error": "Failed to get access token"}), 500

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 1. Fetch activities, bills, or line items for the matter from Clio API
    # (Adjust endpoints based on your exact Clio data structure)
    activities_res = requests.get(f"https://app.clio.com/api/v4/activities.json?matter_id={matter_id}", headers=headers).json()
    bills_res = requests.get(f"https://app.clio.com/api/v4/bills.json?matter_id={matter_id}", headers=headers).json()

    # 2. Run your specific calculations
    total_activities = sum(float(act.get("total", 0)) for act in activities_res.get("data", []))
    # Add your specific rules (e.g., publication expenses, subtracting payments)
    # total_balance = total_activities - total_payments 

    # 3. Push the calculated result back to Clio custom fields
    update_payload = {
        "matter": {
            "custom_field_values": [
                {
                    # Replace with your actual custom field ID or name mapping
                    "field_name": "Calculated Balance", 
                    "value": total_activities
                }
            ]
        }
    }
    
    update_res = requests.patch(f"https://app.clio.com/api/v4/matters/{matter_id}.json", headers=headers, json=update_payload)
    print(f"Clio update response: {update_res.status_code}")

    return jsonify({"status": "processed", "calculated_total": total_activities}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
