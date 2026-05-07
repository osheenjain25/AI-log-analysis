import huaweicloudsdkbss.v2 as bss_v2
import inspect

print("Classes in huaweicloudsdkbss.v2:")
for name, obj in inspect.getmembers(bss_v2):
    if inspect.isclass(obj) and "Request" in name:
        print(f"  {name}")

print("\nInspecting MonthlyBillRes:")
from huaweicloudsdkbss.v2 import MonthlyBillRes
print(inspect.signature(MonthlyBillRes.__init__))
print(MonthlyBillRes().to_dict().keys())
