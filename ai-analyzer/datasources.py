import abc
import os
import json
import time
import requests
import boto3
from botocore.exceptions import ClientError

class DataSource(abc.ABC):
    @abc.abstractmethod
    def fetch_logs(self, start_time=None):
        """Fetch new logs since start_time"""
        pass

    @abc.abstractmethod
    def validate_access(self):
        """Check if this datasource is authorized"""
        pass

class LokiDataSource(DataSource):
    def __init__(self, loki_url, job_name):
        self.loki_url = loki_url.rstrip('/')
        self.job_name = job_name
        self.allowed_jobs = os.getenv("ALLOWED_LOKI_JOBS", "").split(",")

    def validate_access(self):
        if not self.allowed_jobs or self.allowed_jobs == ['']:
            return True # Default to allow all if env var not set
        
        if self.job_name not in self.allowed_jobs:
            raise PermissionError(f"Unauthorized Loki Job: {self.job_name}. Allowed: {self.allowed_jobs}")
        return True

    def fetch_logs(self, start_time=None):
        if not start_time:
            start_time = int((time.time() - 300) * 1000000000)
            
        query = f'{{exporter="OTLP", job="{self.job_name}"}}'
        params = {
            'query': query,
            'start': start_time,
            'limit': 1000
        }
        
        try:
            response = requests.get(f"{self.loki_url}/loki/api/v1/query_range", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            logs = []
            max_timestamp = start_time
            
            if 'data' in data and 'result' in data['data']:
                for stream in data['data']['result']:
                    for value in stream['values']:
                        timestamp = int(value[0])
                        if timestamp > start_time:
                            logs.append(value)
                            if timestamp > max_timestamp:
                                max_timestamp = timestamp
                                
            return logs, max_timestamp
        except Exception as e:
            print(f"Error querying Loki at {self.loki_url}: {e}", flush=True)
            return [], start_time

class OTLPDataSource(DataSource):
    def __init__(self, otel_url, service_name):
        self.otel_url = otel_url.rstrip('/')
        self.service_name = service_name
        self.allowed_services = os.getenv("ALLOWED_OTEL_SERVICES", "").split(",")

    def validate_access(self):
        if not self.allowed_services or self.allowed_services == ['']:
            return True
        if self.service_name not in self.allowed_services:
            raise PermissionError(f"Unauthorized OTEL Service: {self.service_name}")
        return True

    def fetch_logs(self, start_time=None):
        # Placeholder for OTLP query logic (e.g., querying an OTLP-compatible backend like Jaeger or Honeycomb)
        # For now, we simulate or point to a known OTLP query endpoint if available
        print(f"Querying OTLP backend at {self.otel_url} for service {self.service_name}...", flush=True)
        return [], int(time.time() * 1000000000)

class S3DataSource(DataSource):
    def __init__(self, bucket_name, prefix="logs/", region="us-east-1"):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.region = region
        self.allowed_buckets = os.getenv("ALLOWED_S3_BUCKETS", "").split(",")
        self.s3 = boto3.client('s3', region_name=region)
        self.processed_files = set()

    def validate_access(self):
        if not self.allowed_buckets or self.allowed_buckets == ['']:
             if os.getenv("ENV") == "development": return True
             raise PermissionError("Security: ALLOWED_S3_BUCKETS must be set.")
        if self.bucket_name not in self.allowed_buckets:
            raise PermissionError(f"Unauthorized S3 Bucket: {self.bucket_name}")
        return True

    def fetch_logs(self, start_time=None):
        logs = []
        # print(f"DEBUG: Fetching logs from S3 bucket {self.bucket_name} prefix {self.prefix}", flush=True)
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=self.prefix)
            if 'Contents' in response:
                # print(f"DEBUG: Found {len(response['Contents'])} objects in S3", flush=True)
                
                # Sort by LastModified to process oldest first (or newest?)
                # Actually, we want to process only new files since start_time
                sorted_objects = sorted(response['Contents'], key=lambda x: x['LastModified'])
                
                for obj in sorted_objects:
                    key = obj['Key']
                    
                    # Skip if already processed
                    if key in self.processed_files:
                        continue
                    
                    if not key.endswith('.json'):
                        continue
                        
                    # Filter by timestamp from filename if start_time is provided
                    # Key format: .../logs_TIMESTAMP.json
                    if start_time:
                        try:
                            # Extract timestamp from filename
                            filename = key.split('/')[-1]
                            ts_part = filename.replace('logs_', '').replace('.json', '')
                            file_ts = int(ts_part) * 1000000000 # Convert to ns
                            
                            # If file is older than start_time, skip it
                            # But wait, start_time is usually the last query time.
                            # If we restart, start_time is None (or recent).
                            # If start_time is None, we default to 5 mins ago in LokiDataSource, but here?
                            if file_ts < start_time:
                                # Mark as processed so we don't check it again?
                                # Yes, but only if we are sure we don't need it.
                                self.processed_files.add(key)
                                continue
                        except ValueError:
                            pass # If parsing fails, process it anyway
                        
                    try:
                        # print(f"DEBUG: Reading file {key}", flush=True)
                        file_obj = self.s3.get_object(Bucket=self.bucket_name, Key=key)
                        content = file_obj['Body'].read().decode('utf-8')
                        
                        # Handle line-delimited JSON
                        for line in content.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                log_entry = json.loads(line)
                                logs.append(log_entry)
                            except json.JSONDecodeError:
                                print(f"Skipping malformed JSON line in {key}", flush=True)
                        
                        self.processed_files.add(key)
                        
                        # Limit to avoid OOM or timeout on first run
                        if len(logs) > 5000:
                            print(f"DEBUG: Reached log limit (5000), stopping fetch.", flush=True)
                            break
                            
                    except Exception as e:
                        print(f"Error reading S3 file {key}: {e}", flush=True)
            # else:
            #     print("DEBUG: No 'Contents' in S3 response", flush=True)
        except Exception as e:
            print(f"Error listing S3 objects in bucket {self.bucket_name}: {e}", flush=True)
            
        print(f"DEBUG: Returning {len(logs)} logs", flush=True)
        return logs, int(time.time() * 1000000000)

class AzureBlobDataSource(DataSource):
    def __init__(self, container_name, prefix="logs/"):
        self.container_name = container_name
        self.prefix = prefix
        self.allowed_containers = os.getenv("ALLOWED_AZURE_CONTAINERS", "").split(",")
        # Placeholder for Azure SDK initialization
        print(f"Initializing Azure Blob Storage for container: {container_name}", flush=True)

    def validate_access(self):
        if not self.allowed_containers or self.allowed_containers == ['']:
            if os.getenv("ENV") == "development": return True
            raise PermissionError("Security: ALLOWED_AZURE_CONTAINERS must be set.")
        if self.container_name not in self.allowed_containers:
            raise PermissionError(f"Unauthorized Azure Container: {self.container_name}")
        return True

    def fetch_logs(self, start_time=None):
        print(f"Fetching logs from Azure Blob Container: {self.container_name}", flush=True)
        return [], int(time.time() * 1000000000)

class GCSDataSource(DataSource):
    def __init__(self, bucket_name, prefix="logs/"):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.allowed_buckets = os.getenv("ALLOWED_GCS_BUCKETS", "").split(",")
        # Placeholder for GCS SDK initialization
        print(f"Initializing GCS for bucket: {bucket_name}", flush=True)

    def validate_access(self):
        if not self.allowed_buckets or self.allowed_buckets == ['']:
            if os.getenv("ENV") == "development": return True
            raise PermissionError("Security: ALLOWED_GCS_BUCKETS must be set.")
        if self.bucket_name not in self.allowed_buckets:
            raise PermissionError(f"Unauthorized GCS Bucket: {self.bucket_name}")
        return True

    def fetch_logs(self, start_time=None):
        print(f"Fetching logs from GCS Bucket: {self.bucket_name}", flush=True)
        return [], int(time.time() * 1000000000)
