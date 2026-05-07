
import os
import json
from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkbss.v2 import BssClient, ListCustomerselfResourceRecordDetailsRequest, QueryResRecordsDetailReq
from huaweicloudsdkbss.v2.region.bss_region import BssRegion

def inspect_real():
    ak = os.getenv("HUAWEI_ACCESS_KEY")
    sk = os.getenv("HUAWEI_SECRET_ACCESS_KEY")
    region = os.getenv("HUAWEI_REGION", "ap-southeast-1")
    
    if not ak or not sk:
        print("Credentials not found in env")
        return

    credentials = GlobalCredentials(ak, sk)
    builder = BssClient.new_builder().with_credentials(credentials)
    
    if region == 'cn-north-1':
        builder.with_region(BssRegion.value_of(region))
    else:
        builder.with_endpoint("https://bss-intl.myhuaweicloud.com")
        
    client = builder.build()

    for cycle in ["2026-01", "2025-12", "2025-11"]:
        print(f"\n--- Cycle: {cycle} ---")
        req = QueryResRecordsDetailReq(cycle=cycle, limit=100, bill_type=1)
        
        unique_dates = {}
        for offset in [0, 100, 200, 300, 400]:
            req.offset = offset
            try:
                request = ListCustomerselfResourceRecordDetailsRequest(body=req)
                resp = client.list_customerself_resource_record_details(request)
                if resp.fee_records:
                    for record in resp.fee_records:
                        d = getattr(record, 'consume_time', None) or getattr(record, 'bill_date', None)
                        tid = getattr(record, 'trade_id', None)
                        if tid and tid.startswith('CS'):
                            date_from_tid = f"20{tid[2:4]}-{tid[4:6]}-{tid[6:8]}"
                        else:
                            date_from_tid = "N/A"
                        
                        date_key = d[:10] if d else f"TID:{date_from_tid}"
                        if date_key not in unique_dates:
                            unique_dates[date_key] = {"tid": tid, "consume_time": d}
                else:
                    break
            except Exception as e:
                print(f"Error: {e}")
                break
        
        for date, info in sorted(unique_dates.items()):
            print(f"Date: {date} | TID: {info['tid']} | ConsumeTime: {info['consume_time']}")

if __name__ == "__main__":
    inspect_real()
