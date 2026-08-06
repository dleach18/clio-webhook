import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Hardcoded custom field IDs for your Clio account
FIELD_IDS = {
    "principal_balance": "22619285",
    "interest": "22639280",
    "total_payments": "22619375",
    "publication_costs": "23054810",
    "total_legal_fees_expenses": "23054825",
    "total_past_due": "22808180"
}

def get_clio_headers():
    return {
        "Authorization": f"Bearer {os.environ.get('CLIO_ACCESS_TOKEN')}",
        "Content-Type": "application/json"
    }

def get_matter_custom_field(matter_data, field_id):
    """Helper to extract a custom field value by its ID from the matter payload."""
    for cf in matter_data.get("custom_field_values", []):
        if str(cf.get("id")) == str(field_id):
            val = cf.get("value")
            return float(val) if val is not None else 0.0
    return 0.0

def calculate_and_update_matter(matter_id):
    headers = get_clio_headers()
    
    # 1. Fetch full matter details to read current custom field values
    matter_res = requests.get(f"https://app.clio.com/api/v4/matters/{matter_id}.json?expand=custom_field_values", headers=headers)
    if matter_res.status_code != 200:
        print(f"Failed to fetch matter {matter_id}: {matter_res.text}")
        return
    
    matter_data = matter_res.json().get("data", {})
    
    # Extract manual fields
    principal_balance = get_matter_custom_field(matter_data, FIELD_IDS["principal_balance"])
    total_payments = get_matter_custom_field(matter_data, FIELD_IDS["total_payments"])
    publication_costs = get_matter_custom_field(matter_data, FIELD_IDS["publication_costs"])
    
    # 2. Fetch all billable activities for this matter to sum up billable amounts
    activities_res = requests.get(f"https://app.clio.com/api/v4/activities.json?matter_id={matter_id}", headers=headers)
    billable_activities_total = 0.0
    
    if activities_res.status_code == 200:
        activities = activities_res.json().get("data", [])
        for act in activities:
            total_val = act.get("total")
            if total_val:
                billable_activities_total += float(total_val)
                
    # 3. Perform Calculations based on your formulas:
    # Total Legal Fees & Expenses = Publication Costs + billable activities amount
    total_legal_fees_expenses = publication_costs + billable_activities_total
    
    # Total Past Due = Total Legal Fees & Expenses + Principal Balance - Total Payments
    total_past_due = total_legal_fees_expenses + principal_balance - total_payments
    
    # 4. Push Updated Values Back to Clio
    payload = {
        "data": {
            "custom_field_values": [
                {
                    "id": FIELD_IDS["total_legal_fees_expenses"],
                    "value": round(total_legal_fees_expenses, 2)
                },
                {
                    "id": FIELD_IDS["total_past_due"],
                    "value": round(total_past_due, 2)
                }
            ]
        }
    }
    
    update_res = requests.patch(
        f"https://app.clio.com/api/v4/matters/{matter_id}.json",
        headers=headers,
        json=payload
    )
    
    print(f"Clio Update Response for Matter {matter_id}: {update_res.status_code} - {update_res.text}")

@app.route("/webhook", methods=["POST"])
def webhook():
    event_data = request.json
    if not event_data:
        return jsonify({"status": "ignored"}), 400
        
    model = event_data.get("model")
    data = event_data.get("data", {})
    
    matter_id = None
    if model == "Matter":
        matter_id = data.get("id")
    elif model == "Activity":
        matter = data.get("matter", {})
        matter_id = matter.get("id")
        
    if matter_id:
        calculate_and_update_matter(matter_id)
        return jsonify({"status": "success"}), 200
        
    return jsonify({"status": "no matter id found"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
