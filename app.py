import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("CLIO_ACCESS_TOKEN")
PUBLICATION_COSTS_FIELD_ID = int(os.environ.get("PUBLICATION_COSTS_FIELD_ID", 0))
TOTAL_LEGAL_FEES_EXPENSES_FIELD_ID = int(os.environ.get("TOTAL_LEGAL_FEES_EXPENSES_FIELD_ID", 0))

BASE_URL = "https://app.clio.com/api/v4"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

@app.route("/", methods=["GET"])
def home():
    return "Clio Webhook Server Running", 200

@app.route("/webhook", methods=["POST"])
def handle_clio_event():
    payload = request.json or {}
    data = payload.get("data", {})
    matter_id = data.get("matter", {}).get("id")
    
    if matter_id and PUBLICATION_COSTS_FIELD_ID and TOTAL_LEGAL_FEES_EXPENSES_FIELD_ID:
        recalculate_matter_total(matter_id)
        
    return jsonify({"status": "received"}), 200

def recalculate_matter_total(matter_id):
    matter_res = requests.get(
        f"{BASE_URL}/matters/{matter_id}.json",
        headers=HEADERS,
        params={"fields": "id,custom_field_values{id,value,custom_field{id}}"}
    )
    if matter_res.status_code != 200:
        return
    matter = matter_res.json().get("data", {})
    
    act_res = requests.get(
        f"{BASE_URL}/activities.json",
        headers=HEADERS,
        params={"matter_id": matter_id, "fields": "total"}
    )
    if act_res.status_code != 200:
        return
    activities = act_res.json().get("data", [])
    total_billable_activities = sum(float(act.get("total", 0.0)) for act in activities)
    
    publication_costs_val = 0.0
    total_target_instance_id = None
    
    for cfv in matter.get("custom_field_values", []):
        cf_id = cfv["custom_field"]["id"]
        val = float(cfv.get("value") or 0.0)
        
        if cf_id == PUBLICATION_COSTS_FIELD_ID:
            publication_costs_val = val
        elif cf_id == TOTAL_LEGAL_FEES_EXPENSES_FIELD_ID:
            total_target_instance_id = cfv.get("id")

    total_fees_and_expenses = publication_costs_val + total_billable_activities

    cf_data = {
        "custom_field": {"id": TOTAL_LEGAL_FEES_EXPENSES_FIELD_ID},
        "value": f"{total_fees_and_expenses:.2f}"
    }
    if total_target_instance_id:
        cf_data["id"] = total_target_instance_id

    requests.patch(
        f"{BASE_URL}/matters/{matter_id}.json",
        headers=HEADERS,
        json={"data": {"custom_field_values": [cf_data]}}
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
