import boto3
import os
from datetime import datetime, timedelta

def verify_aws():
    print("--- AWS Connection Diagnostic (Extended) ---")
    print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID', 'MISSING')[:4]}...")
    print(f"AWS_REGION: {os.getenv('AWS_REGION', 'MISSING')}")
    
    try:
        client = boto3.client('ce', region_name='us-east-1')
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        print(f"Attempting to fetch cost data from {start_date} to {end_date}...")
        
        # Test with all metrics used in the pipeline
        metrics = ['UnblendedCost', 'AmortizedCost', 'UsageQuantity']
        
        for metric in metrics:
            try:
                print(f"Testing metric: {metric}...")
                response = client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity='DAILY',
                    Metrics=[metric]
                )
                print(f"  ✅ SUCCESS: {metric} is available.")
            except Exception as e:
                print(f"  ❌ FAILURE: {metric} failed. Error: {e}")
                if "AmortizedCost" in metric:
                    print("  TIP: Amortized costs might not be enabled in your Cost Explorer settings.")
        
        print("\nTesting GroupBy with DIMENSIONS...")
        try:
            response = client.get_cost_and_usage(
                TimePeriod={'Start': start_date, 'End': end_date},
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            print("  ✅ SUCCESS: GroupBy dimensions are supported.")
        except Exception as e:
            print(f"  ❌ FAILURE: GroupBy failed. Error: {e}")

    except Exception as e:
        print(f"❌ CRITICAL FAILURE: {e}")

if __name__ == "__main__":
    verify_aws()
