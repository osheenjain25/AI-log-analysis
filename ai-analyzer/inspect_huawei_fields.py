
import os
from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkbss.v2 import BssClient, ListCustomerselfResourceRecordDetailsRequest, QueryResRecordsDetailReq
from huaweicloudsdkbss.v2.region.bss_region import BssRegion

def inspect_fields():
    ak = os.getenv("HUAWEI_ACCESS_KEY")
    sk = os.getenv("HUAWEI_SECRET_ACCESS_KEY")
    region = os.getenv("HUAWEI_REGION", "ap-southeast-1")
    
    if not ak or not sk:
        print("Credentials not found")
        return

    credentials = GlobalCredentials(ak, sk)
    client = BssClient.new_builder().with_credentials(credentials).with_region(BssRegion.value_of("cn-north-1")).build()
    
    # Use international endpoint if needed
    if region != 'cn-north-1':
         client = BssClient.new_builder().with_credentials(credentials).with_endpoint("https://bss-intl.myhuaweicloud.com").build()

    request = ListCustomerselfResourceRecordDetailsRequest()
    body = QueryResRecordsDetailReq(
        cycle="2026-01"
    )
    request.body = body
    
    try:
        response = client.list_customerself_resource_record_details(request)
        if response.monthly_records:
            record = response.monthly_records[0]
            print("Available fields in record:")
            print(dir(record))
            print("\nRecord details:")
            print(record.to_str())
        else:
            print("No records found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_fields()
