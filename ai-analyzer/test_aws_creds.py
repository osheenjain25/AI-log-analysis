import boto3
import os
from datetime import datetime, timedelta

def test_aws():
    ak = os.getenv('AWS_ACCESS_KEY_ID')
    sk = os.getenv('AWS_SECRET_ACCESS_KEY')
    st = os.getenv('AWS_SESSION_TOKEN')
    
    print(f"Testing with AK: {ak[:5]}..., ST present: {bool(st)}")
    
    try:
        client = boto3.client(
            'ce',
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            aws_session_token=st,
            region_name='us-east-1'
        )
        
        end = datetime.now().date()
        start = end - timedelta(days=1)
        
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': start.strftime('%Y-%m-%d'),
                'End': end.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        print("Success! Fetched cost data.")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_aws()
