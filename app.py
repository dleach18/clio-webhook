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

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Webhook service is live", 200

    # Handle Clio's webhook activation handshake
    hook_secret = request.headers.get("X-Hook-Secret")
    if hook_secret:
        return "", 200, {"X-Hook-Secret": hook_secret}

    event_data = request.json
    print("Received webhook event:", event_data)
    
    try:
        matter_id = (
            event_data.get("data", {}).get("matter", {}).get("id") or 
            event_data.get("data", {}).get("id")
        )
        if not matter_id:
            return jsonify({"status": "ignored, no matter id found"}), 200
    except Exception as e:
        print(f"Error parsing payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400

    access_token = get_access_token()
    if not access_token:
        return jsonify({"error": "Failed to get access token"}), 500

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    matter_res = requests.get(f"https://app.clio.com/api/v4/matters/{matter_id}.json?expand=custom_field_values", headers=headers).json()
    matter_data = matter_res.get("data", {})
    custom_fields = matter_data.get("custom_field_values", [])

    def get_cf_value(field_id):
        for cf in custom_fields:
            cf_id = cf.get("custom_field", {}).get("id") or cf.get("id")
            if cf_id == field_id:
                val = cf.get("value")
                return float(val) if val is not None else 0.0
        return 0.0

    principal_balance = get_cf_value(22619285)
    publication_costs = get_cf_value(23054810)

    activities_res = requests.get(f"https://app.clio.com/api/v4/activities.json?matter_id={matter_id}", headers=headers).json()
    activities = activities_res.get("data", [])
    total_activities = sum(float(act.get("total", 0)) for act in activities)

    bills_res = requests.get(f"https://app.clio.com/api/v4/bills.json?matter_id={matter_id}", headers=headers).json()
    bills = bills_res.get("data", [])
    total_payments = sum(float(bill.get("paid", 0)) for bill in bills)

    total_legal_fees_and_expenses = publication_costs + total_activities
    total_past_due = total_legal_fees_and_expenses + principal_balance - total_payments

    update_payload = {
        "matter": {
            "custom_field_values_attributes": [
                {"id": 23054825, "value": total_legal_fees_and_expenses},
                {"id": 22808180, "value": total_past_due}
            ]
        }
    }

    update_res = requests.patch(
        f"https://app.clio.com/api/v4/matters/{matter_id}.json", 
        headers=headers, 
        json=update_payload
    )
    print(f"Clio update status: {update_res.status_code}", update_res.text)

    return jsonify({
        "status": "success",
        "total_legal_fees_and_expenses": total_legal_fees_and_expenses,
        "total_past_due": total_past_due
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
