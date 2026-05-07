import os
import json
from cost_analyzer import HuaweiCostDataSource

def test_huawei_cost():
    # Credentials from user request
    ak = "HPUAS96PY8VROIIU465K"
    sk = "584tFHlRHomncJLYdMTBHmQvkbsvZPlj3mQXwjhB"
    region = "ap-southeast-1" # Default region or as needed

    print(f"Testing Huawei Cloud Cost Data Source with AK: {ak[:4]}***")
    
    try:
        data_source = HuaweiCostDataSource(ak, sk, region)
        
        # Set a small time period for testing
        data_source.set_time_period(days_back=7)
        print(f"Fetching cost data from {data_source.start_date} to {data_source.end_date}...")
        
        data = data_source.extract_cost_data_by_service_and_usage(granularity='DAILY')
        
        print("\n--- Analysis Result ---")
        print(f"Total Cost: {data['summary']['total_cost']}")
        print(f"Services Found: {data['summary']['services']}")
        print(f"Is Complete: {data['summary']['is_complete']}")
        
        if data['results_by_time']:
            print(f"\nSample Data (First Day):")
            print(json.dumps(data['results_by_time'][0], indent=2))
        else:
            print("\nNo cost data found for this period.")
            
    except Exception as e:
        print(f"\nERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_huawei_cost()
