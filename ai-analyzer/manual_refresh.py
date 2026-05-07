import requests
import json
import datetime
import os

base_url = "http://localhost:5000/analyze-cost"

def get_data(granularity, days):
    try:
        print(f"Fetching {granularity}...", flush=True)
        resp = requests.post(base_url, json={"granularity": granularity, "days": days})
        resp.raise_for_status()
        data = resp.json()
        points = len(data.get('chart_data', {}).get('stacked_bar_data', []))
        print(f"  Received {points} points for {granularity}", flush=True)
        return data
    except Exception as e:
        print(f"Failed {granularity}: {e}", flush=True)
        return {"report": f"Failed: {e}", "metadata": {"is_complete": False}}

def get_huawei_data(granularity, days):
    try:
        print(f"Fetching Huawei {granularity}...", flush=True)
        resp = requests.post(base_url, json={
            "granularity": granularity, 
            "days": days, 
            "provider": "huawei", 
            "account_id": "hw-intl"
        })
        resp.raise_for_status()
        data = resp.json()
        points = len(data.get('chart_data', {}).get('stacked_bar_data', []))
        print(f"  Received {points} points for Huawei {granularity}", flush=True)
        return data
    except Exception as e:
        print(f"Failed Huawei {granularity}: {e}", flush=True)
        return {"report": f"Failed: {e}", "metadata": {"is_complete": False}}

data = {
    "daily": get_data("daily", 31),
    "weekly": get_data("weekly", 377),
    "monthly": get_data("monthly", 377),
    "last_updated": datetime.datetime.now().isoformat()
}

huawei_data = {
    "daily": get_huawei_data("daily", 31),
    "weekly": get_huawei_data("weekly", 377),
    "monthly": get_huawei_data("monthly", 377),
    "last_updated": datetime.datetime.now().isoformat()
}

output_file = "last_cost_analysis.json"
with open(output_file, "w") as f:
    json.dump(data, f)
print(f"Saved AWS data to {output_file}")

huawei_output_file = "last_cost_analysis_huawei_hw-intl.json"
with open(huawei_output_file, "w") as f:
    json.dump(huawei_data, f)
print(f"Saved Huawei data to {huawei_output_file}")
