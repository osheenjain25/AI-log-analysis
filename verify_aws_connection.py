import boto3
import os
from datetime import datetime, timedelta

def test_ce_connection():
    ak = os.getenv('AWS_ACCESS_KEY_ID')
    sk = os.getenv('AWS_SECRET_ACCESS_KEY')
    st = os.getenv('AWS_SESSION_TOKEN')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    print(f"Testing CE connection with Region: {region}")
    print(f"Access Key ID: {ak[:5]}...{ak[-5:] if ak else ''}")
    
    client = boto3.client(
        'ce',
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        aws_session_token=st if st else None,
        region_name=region
    )
    
    end_dt = datetime.now().date()
    start_dt = end_dt - timedelta(days=1)
    
    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start_dt.strftime('%Y-%m-%d'), 'End': end_dt.strftime('%Y-%m-%d')},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        print("Success! Connection established.")
        print(f"Response: {response.get('ResultsByTime', [])}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ce_connection()
