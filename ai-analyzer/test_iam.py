from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest

def test_iam(endpoint, name):
    print(f"Testing IAM endpoint: {endpoint} ({name})")
    ak = "HPUAS96PY8VROIIU465K"
    sk = "584tFHlRHomncJLYdMTBHmQvkbsvZPlj3mQXwjhB"
    
    try:
        credentials = GlobalCredentials(ak, sk)
        client = IamClient.new_builder() \
            .with_credentials(credentials) \
            .with_endpoint(endpoint) \
            .build()
            
        request = KeystoneListProjectsRequest()
        response = client.keystone_list_projects(request)
        print(f"SUCCESS: Found {len(response.projects)} projects.")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    # Test International
    if test_iam("https://iam.myhuaweicloud.com", "International"):
        print("Credentials are for International site.")
    # Test China
    elif test_iam("https://iam.myhuaweicloud.com.cn", "China"):
        print("Credentials are for China site.")
    else:
        print("Credentials failed for both sites.")
