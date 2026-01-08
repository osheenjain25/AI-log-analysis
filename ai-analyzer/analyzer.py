import time
import requests
import json
import os
import re
import logging
import threading
import boto3
from collections import Counter, deque
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from botocore.exceptions import ClientError
from abc import ABC, abstractmethod
import glob
from datasources import LokiDataSource, S3DataSource, OTLPDataSource, AzureBlobDataSource, GCSDataSource
# AI API Configuration (Generic)
DEFAULT_AI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_AI_MODEL = "google/gemini-2.0-flash-exp:free"
# Environment Configuration
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
# Global Configuration
app = Flask(__name__)
CORS(app)
config = {
    "datasource_type": os.getenv("DATASOURCE_TYPE", "s3"), # 'loki', 's3', 'otel', 'azure', 'gcs'
    "datasource": os.getenv("AWS_S3_LOGS_BUCKET", "log-generator"), # Name/Label/Bucket/Container
    "loki_url": LOKI_URL,
    "otel_url": OTEL_ENDPOINT,
    "auth_token": None,
    "ai_api_key": os.getenv("AI_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
    "ai_api_url": os.getenv("AI_API_URL") or ("https://openrouter.ai/api/v1/chat/completions" if os.getenv("OPENROUTER_API_KEY") else DEFAULT_AI_API_URL),
    "ai_model": os.getenv("AI_MODEL") or ("allenai/olmo-3.1-32b-think:free" if os.getenv("OPENROUTER_API_KEY") else DEFAULT_AI_MODEL),
    "aws_region": "us-east-1",
    "s3_prefix": "logs/",
    "insights_bucket": os.getenv("AWS_S3_INSIGHTS_BUCKET") or os.getenv("AWS_S3_LOGS_BUCKET"),
    "logs_bucket": os.getenv("AWS_S3_LOGS_BUCKET")
}
class StorageInterface(ABC):
    @abstractmethod
    def list_files(self, prefix):
        pass
    @abstractmethod
    def read_file(self, path):
        pass
    @abstractmethod
    def write_file(self, path, content):
        pass
    @abstractmethod
    def delete_file(self, path):
        pass
class LocalStorage(StorageInterface):
    def __init__(self, base_path="data"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    def list_files(self, prefix):
        # Local storage implementation returns relative paths to base_path
        search_path = os.path.join(self.base_path, prefix)
        if not os.path.exists(search_path):
            return []
            
        files = []
        for root, _, filenames in os.walk(search_path):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                files.append(os.path.relpath(full_path, self.base_path))
        
        return files
    def read_file(self, path):
        full_path = os.path.join(self.base_path, path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                return f.read()
        return None
    def write_file(self, path, content):
        full_path = os.path.join(self.base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
    def delete_file(self, path):
        full_path = os.path.join(self.base_path, path)
        if os.path.exists(full_path):
            os.remove(full_path)
class S3Storage(StorageInterface):
    def __init__(self, bucket, region):
        self.bucket = bucket
        self.s3 = boto3.client('s3', region_name=region)
    def list_files(self, prefix):
        try:
            paginator = self.s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
            files = []
            for page in pages:
                if 'Contents' in page:
                    files.extend([obj['Key'] for obj in page['Contents']])
            return files
        except ClientError as e:
            print(f"S3 Error: {e}")
            return []
    def read_file(self, path):
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=path)
            return response['Body'].read().decode('utf-8')
        except ClientError as e:
            print(f"S3 Error: {e}")
            return None
    def write_file(self, path, content):
        try:
            self.s3.put_object(Bucket=self.bucket, Key=path, Body=content)
        except ClientError as e:
            print(f"S3 Error: {e}")
    def delete_file(self, path):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=path)
        except ClientError as e:
            print(f"S3 Error: {e}")
def get_storage_backend():
    if config["datasource_type"] == "s3" and config["insights_bucket"]:
        print(f"Using S3 Storage: {config['insights_bucket']}")
        return S3Storage(config["insights_bucket"], config["aws_region"])
    else:
        print("Using Local Storage: ./data")
        return LocalStorage()
class S3LogWriter:
    def __init__(self, bucket, region):
        self.bucket = bucket
        self.s3 = boto3.client('s3', region_name=region)
    def archive_logs(self, logs, datasource_name):
        if not logs:
            return
        
        timestamp = int(time.time())
        now = datetime.now()
        # Key structure: logs/datasource/YYYY/MM/DD/HH/logs_<timestamp>.json
        key = f"logs/{datasource_name}/{now.strftime('%Y/%m/%d/%H')}/logs_{timestamp}.json"
        
        try:
            # Convert logs to line-delimited JSON
            content = ""
            for log in logs:
                content += json.dumps(log) + "\n"
                
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType='application/json'
            )
            print(f"Logs archived to s3://{self.bucket}/{key}", flush=True)
        except Exception as e:
            print(f"Error archiving logs to S3: {e}", flush=True)
class S3InsightWriter:
    def __init__(self, bucket, region):
        self.bucket = bucket
        self.s3 = boto3.client('s3', region_name=region)
        self.buffer = []
        self.lock = threading.Lock()
        self.last_flush = time.time()
        self.flush_interval = 300  # Flush every 5 minutes
        self.batch_size = 50  # Or flush when buffer reaches 50 insights
    def upload_insight(self, insight, timestamp):
        """Add insight to buffer and flush if needed"""
        with self.lock:
            self.buffer.append({
                "timestamp": timestamp,
                "insight": insight,
                "uploaded_at": int(time.time() * 1000000000)
            })
            
            # Flush if buffer is full or enough time has passed
            if len(self.buffer) >= self.batch_size or (time.time() - self.last_flush) > self.flush_interval:
                self._flush()
    def _flush(self):
        """Flush buffered insights to S3 in partitioned structure"""
        if not self.buffer:
            return
            
        insights_to_upload = self.buffer[:]
        self.buffer = []
        self.last_flush = time.time()
        
        try:
            # Group insights by hour for partitioning
            from datetime import datetime
            now = datetime.utcnow()
            partition_key = f"insights/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}/insights_{int(time.time())}.jsonl"
            
            # Create JSONL content
            jsonl_content = "\n".join([json.dumps(item) for item in insights_to_upload])
            
            self.s3.put_object(
                Bucket=self.bucket,
                Key=partition_key,
                Body=jsonl_content,
                ContentType='application/x-ndjson'
            )
            print(f"Uploaded {len(insights_to_upload)} insights to s3://{self.bucket}/{partition_key}", flush=True)
        except Exception as e:
            print(f"Error uploading insights to S3: {e}", flush=True)
            # Re-add to buffer on failure
            with self.lock:
                self.buffer = insights_to_upload + self.buffer
    def flush(self):
        """Public method to force flush"""
        with self.lock:
            self._flush()
class TicketManager:
    def __init__(self, storage_file="/app/data/tickets.json"):
        self.storage_file = storage_file
        self.tickets = self._load_tickets()
        self.lock = threading.Lock()
        print(f"DEBUG: TicketManager initialized with storage: {self.storage_file}", flush=True)
    def _load_tickets(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading tickets: {e}", flush=True)
        return {}
    def _save_tickets(self):
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(self.tickets, f, indent=2)
        except Exception as e:
            print(f"Error saving tickets: {e}", flush=True)
    def create_or_update_ticket(self, unique_key, category, summary, full_text, user_id=None):
        print(f"DEBUG: Creating/Updating ticket for {unique_key}", flush=True)
        with self.lock:
            now = int(time.time() * 1000000000)
            if unique_key in self.tickets:
                # Update existing ticket
                ticket = self.tickets[unique_key]
                ticket["occurrences"] += 1
                ticket["updated_at"] = now
                ticket["title"] = summary # Ensure title is the error summary
                ticket["summary"] = summary
                # Record incident timing
                if "incident_timings" not in ticket:
                    ticket["incident_timings"] = [ticket.get("created_at", now)]
                ticket["incident_timings"].append(now)
                # Ensure first_seen is set
                if "first_seen" not in ticket:
                    ticket["first_seen"] = ticket.get("created_at", now)
                
                # Track affected users
                if "affected_users" not in ticket:
                    ticket["affected_users"] = []
                if user_id and user_id not in ticket["affected_users"]:
                    ticket["affected_users"].append(user_id)
                ticket["user_count"] = len(ticket["affected_users"])
                ticket["blast_radius"] = f"{ticket['user_count']} users affected"
                
                # If resolved, maybe reopen? For now, just track occurrence
                if ticket["status"] == "RESOLVED":
                    ticket["status"] = "REOPENED"
            else:
                # Create new ticket
                self.tickets[unique_key] = {
                    "id": unique_key,
                    "title": summary,
                    "description": full_text,
                    "category": category,
                    "status": "OPEN",
                    "occurrences": 1,
                    "created_at": now,
                    "updated_at": now,
                    "first_seen": now,
                    "incident_timings": [now],
                    "affected_users": [user_id] if user_id else [],
                    "user_count": 1 if user_id else 0,
                    "blast_radius": "1 user affected" if user_id else "No users tracked"
                }
            self._save_tickets()
    def get_tickets(self, status=None):
        with self.lock:
            if status:
                return [t for t in self.tickets.values() if t["status"] == status]
            return list(self.tickets.values())
    def update_status(self, ticket_id, status):
        with self.lock:
            if ticket_id in self.tickets:
                self.tickets[ticket_id]["status"] = status
                self.tickets[ticket_id]["updated_at"] = int(time.time() * 1000000000)
                self._save_tickets()
                return True
            return False
class InsightManager:
    def __init__(self, storage: StorageInterface):
        self.storage = storage
        self.insights_prefix = "insights/"
        self.tickets_prefix = "tickets/"
        self.lock = threading.Lock()
        self.cache = {}  # In-memory cache for insights
        self.last_cache_refresh = 0
        self.cache_ttl = 60  # Cache for 60 seconds
    def save_insight(self, insight_data):
        # Generate a unique filename based on key or timestamp
        key = insight_data.get("key")
        if not key:
            # Create a key if not exists
            summary = insight_data.get("summary", "unknown")
            category = insight_data.get("category", "UNKNOWN")
            summary_key = re.sub(r'[^a-zA-Z0-9]', '_', summary.lower())[:50]
            key = f"{category}:{summary_key}"
            insight_data["key"] = key
        # Sanitize key for filename
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        filename = f"{self.insights_prefix}{safe_key}.json"
        
        # Check if exists to increment count (simple read-modify-write)
        # In a real distributed system, we'd need better locking or a DB
        existing_content = self.storage.read_file(filename)
        if existing_content:
            try:
                existing = json.loads(existing_content)
                insight_data["count"] = existing.get("count", 0) + 1
                insight_data["first_seen"] = existing.get("first_seen", insight_data["last_seen"])
                insight_data["incident_timings"] = existing.get("incident_timings", [insight_data["first_seen"]])
                insight_data["incident_timings"].append(insight_data["last_seen"])
                
                # Track affected users/entities in blast_radius
                affected_users = existing.get("affected_users", set())
                if isinstance(affected_users, list):
                    affected_users = set(affected_users)
                
                # Extract user ID from current log if present
                current_user = insight_data.get("user_id") or insight_data.get("details", {}).get("user_id")
                if current_user:
                    affected_users.add(current_user)
                
                insight_data["affected_users"] = list(affected_users)
                insight_data["user_count"] = len(affected_users)
                
                # Update blast_radius in details
                if "details" not in insight_data:
                    insight_data["details"] = {}
                insight_data["details"]["blast_radius"] = f"{len(affected_users)} users affected"
                
            except:
                # Fallback if JSON is corrupt
                insight_data["count"] = 1
                insight_data["first_seen"] = insight_data["last_seen"]
                insight_data["incident_timings"] = [insight_data["last_seen"]]
                insight_data["affected_users"] = []
                insight_data["user_count"] = 0
        else:
            # New insight initialization
            insight_data["count"] = 1
            insight_data["first_seen"] = insight_data["last_seen"]
            insight_data["incident_timings"] = [insight_data["last_seen"]]
            
            # Initialize affected users tracking
            current_user = insight_data.get("user_id") or insight_data.get("details", {}).get("user_id")
            insight_data["affected_users"] = [current_user] if current_user else []
            insight_data["user_count"] = 1 if current_user else 0
            
            if "details" not in insight_data:
                insight_data["details"] = {}
            if current_user:
                insight_data["details"]["blast_radius"] = "1 user affected"
        self.storage.write_file(filename, json.dumps(insight_data, indent=2))
        
        # Update cache
        with self.lock:
            self.cache[key] = insight_data
            
        return key
    def get_all_insights(self):
        now = time.time()
        
        # 1. Check if refresh is needed
        needs_refresh = False
        with self.lock:
            if not self.cache or (now - self.last_cache_refresh) > self.cache_ttl:
                needs_refresh = True
        
        if needs_refresh:
            # If cache is already present, refresh in background to avoid blocking
            if self.cache:
                threading.Thread(target=self._refresh_cache, daemon=True).start()
            else:
                # If cache is empty, we must refresh synchronously for the first call
                self._refresh_cache()
        
        # 4. Return from cache (quick lock)
        with self.lock:
            insights = list(self.cache.values())
            
        # Sort by last_seen desc
        return sorted(insights, key=lambda x: x.get("last_seen", 0), reverse=True)
    def _refresh_cache(self):
        now = time.time()
        print(f"DEBUG: Refreshing insights cache from storage...", flush=True)
        try:
            # 2. Perform S3 operations OUTSIDE lock
            # Filter for .json files and limit to 100 most recent for performance
            all_files = self.storage.list_files(self.insights_prefix)
            json_files = [f for f in all_files if f.endswith(".json")]
            
            # Sort by name (which usually includes timestamp or is stable) and take last 100
            json_files.sort(reverse=True)
            files_to_read = json_files[:100]
            
            new_cache = {}
            for f in files_to_read:
                content = self.storage.read_file(f)
                if content:
                    try:
                        data = json.loads(content)
                        if "key" in data:
                            new_cache[data["key"]] = data
                    except:
                        pass
            
            # 3. Update cache INSIDE lock
            with self.lock:
                self.cache = new_cache
                self.last_cache_refresh = now
            print(f"DEBUG: Cache refreshed with {len(new_cache)} insights", flush=True)
        except Exception as e:
            print(f"Error refreshing insights cache: {e}", flush=True)
    
    def get_category_distribution(self):
        insights = self.get_all_insights()
        counts = Counter()
        for i in insights:
            counts[i.get("category", "UNKNOWN")] += i.get("count", 1)
        return [{"name": cat, "value": count} for cat, count in counts.items()]
# Initialize Storage and Managers
storage_backend = get_storage_backend()
insight_manager = InsightManager(storage_backend)
ticket_manager = TicketManager()
class GChatNotifier:
    def __init__(self):
        self.webhook_url = os.getenv("GCHAT_WEBHOOK_URL")
        self.last_notified = {} # {unique_key: timestamp}
        self.cooldown = 3600 # 1 hour cooldown
        if not self.webhook_url:
            print("WARNING: GCHAT_WEBHOOK_URL not set. Notifications disabled.", flush=True)
    def send_alert(self, message, severity, insight_text, unique_key, is_anomaly=False):
        if not self.webhook_url:
            return
        # Deduplication logic
        now = time.time()
        if unique_key in self.last_notified:
            if now - self.last_notified[unique_key] < self.cooldown:
                print(f"DEBUG: Skipping GChat alert for {unique_key} (cooldown active)", flush=True)
                return
        try:
            # Determine card color/style based on severity
            header_subtitle = "Critical Alert" if severity == "CRITICAL" else "Anomaly Detected"
            if is_anomaly:
                header_subtitle = "Statistical Anomaly Detected"
            
            # Construct card message
            card = {
                "cards": [
                    {
                        "header": {
                            "title": "AI Log Analyzer Alert",
                            "subtitle": header_subtitle,
                            "imageUrl": "https://www.gstatic.com/images/icons/material/system/2x/warning_amber_48dp.png",
                            "imageStyle": "IMAGE"
                        },
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "keyValue": {
                                            "topLabel": "Severity",
                                            "content": severity,
                                            "contentMultiline": "false"
                                        }
                                    },
                                    {
                                        "keyValue": {
                                            "topLabel": "Log Message",
                                            "content": message[:200] + ("..." if len(message) > 200 else ""),
                                            "contentMultiline": "true"
                                        }
                                    },
                                    {
                                        "keyValue": {
                                            "topLabel": "AI Insight",
                                            "content": insight_text[:500] + ("..." if len(insight_text) > 500 else ""),
                                            "contentMultiline": "true"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            response = requests.post(self.webhook_url, json=card, timeout=5)
            if response.status_code == 200:
                print(f"DEBUG: GChat alert sent successfully for {unique_key}.", flush=True)
                self.last_notified[unique_key] = now # Update last notified time
            else:
                print(f"ERROR: Failed to send GChat alert. Status: {response.status_code}, Response: {response.text}", flush=True)
        except Exception as e:
            print(f"ERROR: Exception sending GChat alert: {e}", flush=True)
class MLLogAnalyzer:
    def __init__(self):
        print("Initializing AI Analyzer with Generic AI API...", flush=True)
        
        # Track error patterns for anomaly detection
        self.error_counter = Counter()
        self.recent_errors = deque(maxlen=100)
        self.baseline_error_rate = 0.15  # Expected 15% error rate
        self.ai_cache = {} # Cache for AI results: {masked_message: insight}
        self.cache_lock = threading.Lock()
        self.notifier = GChatNotifier()
        
    def mask_pii(self, text):
        """Sanitize sensitive information before sending to AI"""
        if not text:
            return ""
            
        # Email
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', text)
        # IP Address (IPv4)
        text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_ADDRESS]', text)
        # Credit Card (simple pattern)
        text = re.sub(r'\b(?:\d{4}[- ]?){3}\d{4}\b', '[CREDIT_CARD]', text)
        # SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        # Phone
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        
        return text
        
    def detect_anomaly(self, severity):
        """Statistical anomaly detection based on error rate"""
        self.recent_errors.append(1 if severity in ["ERROR", "CRITICAL"] else 0)
        
        if len(self.recent_errors) >= 20:
            current_error_rate = sum(self.recent_errors) / len(self.recent_errors)
            if current_error_rate > self.baseline_error_rate * 2:
                return True, current_error_rate
        return False, 0
    def get_rule_based_fallback(self, message, severity, attributes):
        """Provide structured fallback insights for common error patterns when AI is unavailable"""
        msg_lower = message.lower()
        
        rules = [
            # Functional errors - expected business logic (IS_EXPECTED: true)
            (r"inventory check failed|out of stock", "APPLICATION ERRORS", "Inventory check failed: item out of stock.", "The requested item is currently unavailable in the warehouse.", "Wait for restock or suggest alternative products.", "Functional inventory limit reached.", "true"),
            (r"invalid coupon code", "USER IMPACT", "Invalid coupon code entered.", "User attempted to use an invalid or expired discount code.", "Verify coupon validity or provide a new code.", "User input error or expired promotion.", "true"),
            (r"coupon.*expired", "USER IMPACT", "Expired coupon code used.", "User attempted to use a coupon that is no longer valid.", "Check promotion dates and update user communication.", "Expired marketing campaign.", "true"),
            (r"refund request denied|policy violation", "APPLICATION ERRORS", "Refund request denied.", "A refund request was rejected due to policy violations.", "Review refund policy and user eligibility.", "Standard policy enforcement.", "true"),
            
            # System failures - unexpected infrastructure issues (IS_EXPECTED: false)
            (r"payment gateway connection failed|payment validation failed", "APPLICATION ERRORS", "Payment gateway connection failure.", "Users are unable to complete checkout transactions.", "Check payment gateway status and network connectivity.", "External payment provider timeout.", "false"),
            (r"database connection lost", "INFRASTRUCTURE", "Database connection lost.", "Application cannot read or write data.", "Check database service status and connection pool settings.", "Database service restart or network partition.", "false"),
            (r"database lock timeout", "INFRASTRUCTURE", "Database lock contention.", "Concurrent updates are causing database locks to time out.", "Optimize database queries and check for long-running transactions.", "High concurrency on specific database rows.", "false"),
            (r"cache service unavailable", "INFRASTRUCTURE", "Cache service unavailable.", "Increased latency and load on the primary database.", "Check Redis/Memcached service status.", "Cache cluster node failure.", "false"),
            (r"search index corruption", "DATA PIPELINES", "Search index corruption detected.", "Product searches may return incomplete or incorrect results.", "Trigger a search index rebuild.", "Disk error or unexpected service shutdown.", "false"),
            (r"elasticsearch cluster status: red|cluster unhealthy", "INFRASTRUCTURE", "Search cluster unhealthy.", "The search cluster is in a critical state and may not serve requests.", "Check Elasticsearch node health and disk space.", "Cluster node failure or resource exhaustion.", "false"),
            (r"network timeout.*product details|search service timeout", "DISTRIBUTED SYSTEMS", "Network timeout loading details.", "Product detail pages or search results are failing to load for users.", "Check internal service mesh and network latency.", "Inter-service communication failure.", "false"),
            (r"mfa verification timeout", "SECURITY", "MFA verification timeout.", "Users are unable to complete multi-factor authentication.", "Check MFA provider status and network latency.", "Third-party MFA service delay.", "false"),
            (r"suspicious activity detected|security alert", "SECURITY", "Suspicious activity detected.", "A potential security threat has been identified for a user account.", "Review account activity and consider temporary suspension.", "Potential account takeover attempt.", "false"),
            (r"slow query detected", "PERFORMANCE", "Slow database query detected.", "A query is taking longer than the expected threshold, impacting performance.", "Analyze and optimize the slow query, check for missing indexes.", "Unoptimized query or large dataset scan.", "false"),
            (r"tax calculation service unavailable|shipping calculator failed", "DISTRIBUTED SYSTEMS", "External service dependency failure.", "A critical third-party service is not responding.", "Check status of external tax/shipping providers.", "Third-party API outage.", "false"),
            (r"third-party tracking api is down|bank api timeout", "DISTRIBUTED SYSTEMS", "External API timeout.", "Communication with an external API has timed out.", "Check connectivity and status of external partners.", "External partner service degradation.", "false"),
            (r"system anomaly|global dns resolution failure|region.*outage|api key revoked|root certificate expiration", "INFRASTRUCTURE", "Critical system anomaly.", "A major systemic issue is impacting service availability.", "Check global infrastructure status (DNS, Cloud Provider, Certs).", "Major infrastructure failure.", "false"),
            (r"storage quota exceeded|avatar upload failed", "INFRASTRUCTURE", "Storage capacity reached.", "Users are unable to upload files due to storage limits.", "Check storage utilization and increase quotas if necessary.", "Disk space or quota exhaustion.", "false")
        ]
        for pattern, category, summary, root_cause, action, anomaly, is_expected in rules:
            if re.search(pattern, msg_lower):
                print(f"DEBUG: Using rule-based fallback for: {summary}", flush=True)
                return f"{category} | {summary} | ROOT_CAUSE: {root_cause} | BLAST_RADIUS: High | ACTIONABLE_FIX: {action} | ANOMALY_CONTEXT: {anomaly} | IS_EXPECTED: {is_expected}"
        # Default fallback if no rule matches
        return None
    def analyze_with_llm(self, message, severity, attributes):
        """Call Generic AI API (OpenAI-compatible) for deep technical analysis"""
        api_key = config.get("ai_api_key")
        api_url = config.get("ai_api_url", DEFAULT_AI_API_URL)
        model = config.get("ai_model", DEFAULT_AI_MODEL)
        # Try cache first
        with self.cache_lock:
            if message in self.ai_cache:
                print(f"DEBUG: AI Cache Hit for: {message[:30]}", flush=True)
                return self.ai_cache[message]
        # Try rule-based fallback first if API key is missing or for specific errors
        print(f"DEBUG: Getting fallback for: {message[:30]}", flush=True)
        fallback = self.get_rule_based_fallback(message, severity, attributes)
        
        # Optimization: If using a free model, use fallback for background analysis to save rate limit for chat
        is_free_model = ":free" in model
        is_background = attributes.get("is_background", False)
        if is_free_model and is_background:
            print(f"DEBUG: Free model detected for background analysis, using fallback to save rate limit.", flush=True)
            result = fallback or f"ANALYSIS FALLBACK | {severity} event detected. (Background AI disabled for free models)"
            with self.cache_lock:
                self.ai_cache[message] = result
            return result

        if not api_key:
            print(f"DEBUG: No API key, using fallback", flush=True)
            result = fallback or "INFRASTRUCTURE | AI API Key Missing. | ROOT_CAUSE: No API key configured for AI analysis. | BLAST_RADIUS: AI analysis features are disabled. | ACTIONABLE_FIX: Add OPENROUTER_API_KEY to your .env file. | ANOMALY_CONTEXT: Configuration missing. | IS_EXPECTED: false"
            with self.cache_lock:
                self.ai_cache[message] = result
            return result
        print(f"DEBUG: Calling AI API at {api_url} with model {model}", flush=True)
        prompt = f"""
        Analyze the provided logs and provide high-value technical insights.
        
        LOG CONTENT (Sanitized):
        {self.mask_pii(message)}
        
        CRITICAL RULES:
        1. **STRICT PII REDACTION**: DO NOT include specific identifiers like User IDs, Session IDs, API Keys, Authentication tokens, Metamask keys, IP addresses, specific file paths, or Product Names in the [SUMMARY] or technical sections. Use generic terms (e.g., "a user", "the database", "an item").
        2. **CANONICAL SUMMARIES**: Ensure that identical types of errors result in the EXACT same [SUMMARY] text to allow for aggregation. Remove variable parts like timestamps, IDs, or specific values from the summary.
           - BAD: "User 123 failed to login at 10:00"
           - GOOD: "User login failed due to invalid credentials."
        3. **CATEGORIZATION**: Categorize the log into EXACTLY one of these 8 categories:
           - **APPLICATION ERRORS**: Code bugs, unhandled exceptions, logic errors, or application-level failures (e.g., "NullPointerException", "IndexOutOfBounds").
           - **INFRASTRUCTURE**: Server, database, network, OS, or hardware level issues (e.g., "Disk full", "DB connection lost", "DNS failure").
           - **DISTRIBUTED SYSTEMS**: Timeouts, connection failures, or coordination issues between microservices or external APIs (e.g., "Service A timeout calling Service B").
           - **CI/CD**: Deployment failures, build errors, configuration drift, or pipeline issues (e.g., "Jenkins build failed", "K8s deployment rollout failed").
           - **DATA PIPELINES**: ETL failures, data corruption, schema mismatches, or data processing issues (e.g., "Spark job failed", "Schema mismatch in Kafka").
           - **SECURITY**: Authentication failures, unauthorized access, potential attacks, or security policy violations (e.g., "Invalid password", "Unauthorized access attempt").
           - **PERFORMANCE**: High latency, resource exhaustion, slow queries, or bottleneck issues (e.g., "Slow query detected", "CPU usage > 90%").
           - **USER IMPACT**: Functional errors directly visible to or blocking the user that are NOT necessarily system failures (e.g., "Payment failed", "Invalid coupon", "Item out of stock").
        4. **ACTIONABLE FIXES**: The `ACTIONABLE_FIX` must be a specific, step-by-step command or check. Avoid generic advice like "Investigate the issue".
           - BAD: "Check the database."
           - GOOD: "Check RDS CPU utilization and connection pool limits."
        5. **CONTEXTUAL ANALYSIS**: In `ANOMALY_CONTEXT`, mention if this appears to be a recurring pattern or an isolated incident based on the provided attributes (e.g., "High frequency in production").
        6. **CLASSIFY AS EXPECTED**: If the error is a standard functional result (e.g., invalid input, out of stock, expired coupon) and NOT a system failure, mark IS_EXPECTED: true. Otherwise, false.
        FORMAT:
        <CATEGORY> | <SUMMARY> | ROOT_CAUSE: <text> | BLAST_RADIUS: <text> | ACTIONABLE_FIX: <text> | ANOMALY_CONTEXT: <text> | IS_EXPECTED: <true/false>
        
        Example:
        APPLICATION ERRORS | Inventory check failed: item out of stock. | ROOT_CAUSE: ...
        
        LOG: {message}
        SEVERITY: {severity}
        ATTRS: {json.dumps(attributes)}
        """
        try:
            # Handle standard OpenAI-compatible chat completions
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a technical SRE analyzer. You only output in the specified format. No conversational filler."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
            
            # Some providers might need different headers, but Bearer auth is standard
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            # Add HTTP Referer/Title for OpenRouter if used
            if "openrouter" in api_url:
                headers["HTTP-Referer"] = "http://localhost:8080"
                headers["X-Title"] = "AI Log Analyzer"
            response = requests.post(
                url=api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=10
            )
            if response.status_code != 200:
                print(f"DEBUG: AI API failed with status {response.status_code}: {response.text[:100]}", flush=True)
                return fallback or f"ANALYSIS ERROR | AI API returned {response.status_code}"
                
            result = response.json()
            print(f"DEBUG: AI API response received", flush=True)
            ai_result = result['choices'][0]['message']['content'].strip()
            
            # Cache the result
            with self.cache_lock:
                self.ai_cache[message] = ai_result
                
            return ai_result
        except Exception as e:
            print(f"DEBUG: AI API Exception: {str(e)}", flush=True)
            return fallback or f"ANALYSIS ERROR | {str(e)}"
    def get_unique_key(self, insight_text, message, attributes):
        """Generate a stable unique key for aggregation and deduplication"""
        # Parse insight text to structured data
        parts = [p.strip() for p in insight_text.split(" | ")]
        
        # Robust category/summary extraction
        valid_categories = ["APPLICATION ERRORS", "INFRASTRUCTURE", "DISTRIBUTED SYSTEMS", "CI/CD", "DATA PIPELINES", "SECURITY", "PERFORMANCE", "USER IMPACT"]
        
        category = "UNKNOWN"
        summary = ""
        
        for part in parts:
            if part.upper() in valid_categories:
                category = part.upper()
                idx = parts.index(part)
                if idx + 1 < len(parts) and ": " not in parts[idx+1]:
                    summary = parts[idx+1]
                break
        
        if not summary:
            # Fallback to masked message
            summary = self.mask_pii(message)[:100]
            print(f"DEBUG: Using masked message for summary: {summary}", flush=True)
        
        # Generalize the summary to remove variable parts (users, codes, items)
        # This ensures the unique key is generic across different users/items
        before_gen = summary
        summary, _ = generalize_message(summary)
        print(f"DEBUG: Generalize summary: '{before_gen}' -> '{summary}'", flush=True)
            
        service_name = attributes.get("service_name", "unknown")
        summary_slug = re.sub(r'[^a-zA-Z0-9]', '_', summary.lower())[:50]
        return f"{service_name}:{category}:{summary_slug}"
    def generate_insight(self, message, severity, attributes):
        """Generate insights using AI and Statistical Analysis"""
        # Check for anomalies (statistical)
        is_anomaly, error_rate = self.detect_anomaly(severity)
        
        # Call AI
        ai_insight = self.analyze_with_llm(message, severity, attributes)
        
        insights = []
        if is_anomaly:
            insights.append(f"🚨 ANOMALY DETECTED: Error rate spiked to {error_rate*100:.1f}%")
        
        if ai_insight:
            insights.append(f"🤖 AI Insight: {ai_insight}")
        
        final_insight = " | ".join(insights) if insights else None
        
        # Generate unique key for this insight
        unique_key = "unknown"
        if final_insight:
            unique_key = self.get_unique_key(final_insight, message, attributes)
        # Send notification for CRITICAL errors or Anomalies
        # We trigger this even if AI insight is missing, as long as it's CRITICAL or an anomaly
        if severity == "CRITICAL" or is_anomaly:
            print(f"DEBUG: Triggering GChat alert for {severity} (Key: {unique_key})...", flush=True)
            # Use a default insight if AI failed
            alert_insight = final_insight or f"🚨 {severity} event detected. AI analysis unavailable."
            self.notifier.send_alert(message, severity, alert_insight, unique_key, is_anomaly)
            
        return final_insight, unique_key
def mask_pii(message):
    """Redact PII from log messages"""
    # Email masking
    message = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_REDACTED]', message)
    # Credit Card masking (simple regex for 16 digits)
    message = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[CREDIT_CARD_REDACTED]', message)
    # IP Address masking (IPv4)
    message = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_REDACTED]', message)
    return message
def generalize_message(message):
    """
    Generalize a log message by replacing variable parts with placeholders
    and extracting the specific values into a details dictionary.
    """
    details = {}
    generalized = message
    
    # 1. Extract Search Queries
    # Pattern: "query: <term>" or "query <term>"
    query_match = re.search(r'query[:\s]+([a-zA-Z0-9_\-\s]+?)(?:\.\.\.|$)', generalized, re.IGNORECASE)
    if query_match:
        term = query_match.group(1).strip()
        details['search_term'] = term
        # Remove the term entirely for a cleaner summary
        generalized = generalized.replace(term, "").strip()
        if generalized.endswith(":"):
            generalized = generalized[:-1].strip() # Remove trailing colon only
    # 2. Extract User IDs
    # Pattern: "user_<id>", "user <id>", "for user <id>"
    # We iterate to find all occurrences but primarily want to generalize the message
    user_matches = re.findall(r'(user[_\s]+(\d+))', generalized, re.IGNORECASE)
    for full_match, uid in user_matches:
        details['user_id'] = f"user_{uid}" # Store last found user_id
        generalized = generalized.replace(full_match, "user")
    
    # Pattern: "account <id>"
    account_matches = re.findall(r'(account\s+([a-zA-Z0-9_]+))', generalized, re.IGNORECASE)
    for full_match, acc_id in account_matches:
        details['account_id'] = acc_id
        generalized = generalized.replace(full_match, "account")
    # 3. Extract Item/Product IDs
    # Pattern: "item <id>", "product <id>"
    item_matches = re.findall(r'((?:item|product)[_\s]+([a-zA-Z0-9_]+))', generalized, re.IGNORECASE)
    for full_match, item_id in item_matches:
        details['item_id'] = item_id
        generalized = generalized.replace(full_match, "item")
        
    # 4. Extract Coupon Codes
    # Pattern: "coupon code: <code >"
    coupon_match = re.search(r'coupon code[:\s]+([a-zA-Z0-9_]+)', generalized, re.IGNORECASE)
    if coupon_match:
        code = coupon_match.group(1)
        details['coupon_code'] = code
        # Remove the code entirely
        generalized = generalized.replace(code, "").strip()
        if generalized.endswith(":"):
            generalized = generalized[:-1].strip() # Remove trailing colon only
            
    # Final safety check: if generalized is empty, return original message
    if not generalized.strip():
        return message, details
        
    return generalized, details
def analyze_log(log_entry, ml_analyzer):
    # Handle both Loki format (list) and S3 format (dict)
    if isinstance(log_entry, list):
        try:
            log_data = json.loads(log_entry[1])
            message = log_data.get("body", "")
            severity = log_data.get("severity", "")
            attributes = log_data.get("attributes", {})
        except json.JSONDecodeError:
            message = log_entry[1]
            severity = ""
            attributes = {}
    elif isinstance(log_entry, dict):
        message = log_entry.get("message", "") or log_entry.get("body", "")
        severity = log_entry.get("severity") or log_entry.get("level", "INFO")
        attributes = log_entry.get("attributes", {})
    else:
        return None, None
    
    # Only analyze ERROR and CRITICAL logs
    if severity not in ["ERROR", "CRITICAL"]:
        # print(f"DEBUG: Skipping log with severity {severity}", flush=True)
        return None, None
    
    # Mask PII before analysis
    masked_message = mask_pii(message)
    
    # Generate comprehensive insight using LLM
    print(f"DEBUG: Analyzing log with severity {severity}: {masked_message[:50]}...", flush=True)
    # Mark as background to allow prioritization
    attributes["is_background"] = True
    return ml_analyzer.generate_insight(masked_message, severity, attributes)
def analysis_loop():
    print(f"Starting AI Analyzer Loop (Storage-First Mode)...", flush=True)
    
    # Initialize ML analyzer
    ml_analyzer = MLLogAnalyzer()
    processed_files = set()
    
    while True:
        try:
            # 1. Discover all environments and services to poll specific prefixes
            now = datetime.now()
            from datetime import timedelta
            prev_hour = now - timedelta(hours=1)
            
            hour_path = now.strftime('%Y/%m/%d/%H')
            prev_hour_path = prev_hour.strftime('%Y/%m/%d/%H')
            
            print(f"DEBUG: Discovering logs for hours: {hour_path}, {prev_hour_path}", flush=True)
            
            log_files = []
            try:
                # 1. Discover all environments and services to poll specific prefixes
                if hasattr(storage_backend, 's3'):
                    # Get environments (production, staging, etc.)
                    resp = storage_backend.s3.list_objects_v2(Bucket=storage_backend.bucket, Prefix="logs/", Delimiter="/")
                    envs = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
                    print(f"DEBUG: Found environments: {envs}", flush=True)
                    
                    for env_prefix in envs:
                        # Get services in this environment
                        resp = storage_backend.s3.list_objects_v2(Bucket=storage_backend.bucket, Prefix=env_prefix, Delimiter="/")
                        services = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
                        print(f"DEBUG: Found services in {env_prefix}: {services}", flush=True)
                        
                        for svc_prefix in services:
                            # Poll current hour
                            current_prefix = f"{svc_prefix}{hour_path}/"
                            found_current = storage_backend.list_files(current_prefix)
                            log_files.extend(found_current)
                            
                            # Poll previous hour
                            prev_prefix = f"{svc_prefix}{prev_hour_path}/"
                            found_prev = storage_backend.list_files(prev_prefix)
                            log_files.extend(found_prev)
                else:
                    # Fallback for local storage
                    # Ensure we only get files, not directories
                    log_files = storage_backend.list_files("logs")
            except Exception as e:
                print(f"Error discovering logs: {e}", flush=True)
            
            print(f"DEBUG: Found {len(log_files)} log files to check", flush=True)
            
            # Sort to process newest first (reverse chronological)
            log_files.sort(reverse=True)
            
            for log_file in log_files:
                print(f"DEBUG: Processing file: {log_file}", flush=True)
                # Skip if already processed
                if log_file in processed_files or log_file.endswith(".processed"):
                    print(f"DEBUG: Skipping already processed file: {log_file}", flush=True)
                    continue
                    
                content = storage_backend.read_file(log_file)
                if not content:
                    print(f"DEBUG: No content in file: {log_file}", flush=True)
                    continue
                    
                # Parse logs (handle JSON array or NDJSON)
                logs = []
                try:
                    # Try as standard JSON array
                    data = json.loads(content)
                    logs = data if isinstance(data, list) else [data]
                except json.JSONDecodeError:
                    # Try as NDJSON
                    for line in content.splitlines():
                        if not line.strip(): continue
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            # Fallback to plain text
                            logs.append({"message": line, "severity": "INFO"})
                for log in logs:
                    # Extract fields for consistent processing and ticket creation
                    if isinstance(log, dict):
                        message = log.get("message", "") or log.get("body", "") or str(log)
                        attributes = log.get("attributes", {})
                    else:
                        message = str(log)
                        attributes = {}
                        
                    # Use the standard analyze_log function to ensure consistent processing
                    # (PII masking, anomaly detection, and GChat notifications)
                    insight_text, unique_key = analyze_log(log, ml_analyzer)
                    if insight_text and unique_key:
                        print(f"DEBUG: AI Result: {insight_text[:100]}...", flush=True)
                        
                        # Parse insight text to structured data
                        parts = [p.strip() for p in insight_text.split(" | ")]
                        
                        # Robust category/summary extraction
                        valid_categories = ["APPLICATION ERRORS", "INFRASTRUCTURE", "DISTRIBUTED SYSTEMS", "CI/CD", "DATA PIPELINES", "SECURITY", "PERFORMANCE", "USER IMPACT"]
                        
                        category = "UNKNOWN"
                        summary = ""
                        
                        for part in parts:
                            # Clean up prefixes
                            clean_part = part.replace("🤖 AI Insight:", "").replace("🚨 ANOMALY DETECTED:", "").strip()
                            # Handle potential double prefixes or extra spaces
                            clean_part = clean_part.split(":", 1)[-1].strip() if ":" in clean_part and clean_part.split(":", 1)[0].strip().upper() not in valid_categories else clean_part
                            if clean_part.upper() in valid_categories:
                                category = clean_part.upper()
                                # If the next part doesn't look like a key-value pair, it's likely the summary
                                idx = parts.index(part)
                                if idx + 1 < len(parts) and ": " not in parts[idx+1]:
                                    summary = parts[idx+1]
                                break
                        
                        # If still UNKNOWN, try the first part if it's not a key-value pair
                        if category == "UNKNOWN" and parts:
                            # Try to extract from the first part if it contains the category
                            first_part = parts[0].replace("🤖 AI Insight:", "").replace("🚨 ANOMALY DETECTED:", "").strip()
                            for valid_cat in valid_categories:
                                if valid_cat in first_part.upper():
                                    category = valid_cat
                                    # Try to get summary from the rest of the string
                                    remaining = first_part[len(valid_cat):].strip()
                                    if remaining.startswith("|") or remaining.startswith(":"):
                                        summary = remaining[1:].strip()
                                    break
                            
                            if category == "UNKNOWN" and ": " not in parts[0]:
                                category = parts[0].replace("🚨 ANOMALY DETECTED: High Error Rate", "").strip()
                                if len(parts) > 1 and ": " not in parts[1]:
                                    summary = parts[1]
                        # Generalize the message to extract details and create a clean summary fallback
                        generalized_message, extracted_details = generalize_message(message)
                        
                        # If summary is still empty or just the masked message, use the generalized message
                        if not summary or summary == mask_pii(message)[:100]:
                            summary = generalized_message[:100]
                        # Ensure summary is generalized even if it came from AI (double check)
                        # This handles cases where AI might repeat the specific variable
                        summary, _ = generalize_message(summary)
                        
                        details = {}
                        for part in parts:
                            if ": " in part:
                                k, v = part.split(": ", 1)
                                details[k.lower().replace(" ", "_")] = v
                        
                        # Merge extracted details
                        details.update(extracted_details)
                        # Extract service metadata from attributes
                        service_name = attributes.get("service_name", "unknown")
                        environment = attributes.get("environment", "unknown")
                        
                        # Extract user ID from attributes or message (priority to extracted_details)
                        user_id = attributes.get("user_id") or details.get("user_id")
                        if not user_id:
                            # Try to extract from message (e.g., "user_123" or "for user 123")
                            user_match = re.search(r'user[_\s]+(\d+)', message, re.IGNORECASE)
                            if user_match:
                                user_id = f"user_{user_match.group(1)}"
                        
                        # Mention service in the summary for better visibility
                        display_summary = f"[{service_name}] {summary}"
                        # Use the unique_key from generate_insight
                        # unique_key = f"{service_name}:{category}:{summary_key}"
                        insight_data = {
                            "key": unique_key,
                            "last_seen": int(time.time() * 1000000000),
                            "raw_text": insight_text,
                            "summary": display_summary,
                            "category": category,
                            "severity": log.get("severity", "ERROR"),
                            "service": service_name,
                            "environment": environment,
                            "details": details,
                            "user_id": user_id  # Add user_id for tracking
                        }
                        
                        # 4. Store Insight
                        stored_key = insight_manager.save_insight(insight_data)
                        print(f"DEBUG: Insight stored with key: {stored_key}", flush=True)
                        
                        # 5. Create/Update Ticket
                        ticket_manager.create_or_update_ticket(unique_key, category, display_summary, insight_text, user_id)
                
                # Mark as processed
                processed_files.add(log_file)
                print(f"Finished processing {log_file}", flush=True)
            
            time.sleep(10)  # Poll every 10 seconds
        except Exception as e:
            print(f"Error in analysis loop: {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(10)
@app.route('/insights', methods=['GET'])
def get_insights():
    return jsonify(insight_manager.get_all_insights())
@app.route('/analytics', methods=['GET'])
def get_analytics():
    return jsonify(insight_manager.get_category_distribution())
@app.route('/tickets', methods=['GET'])
def get_tickets():
    status = request.args.get('status')
    return jsonify(ticket_manager.get_tickets(status))
@app.route('/tickets/<path:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    data = request.json
    status = data.get('status')
    if not status:
        return jsonify({"error": "Status is required"}), 400
    
    if ticket_manager.update_status(ticket_id, status):
        return jsonify({"success": True})
    return jsonify({"error": "Ticket not found"}), 404
@app.route('/config', methods=['POST'])
def update_config():
    data = request.json
    
    # Validate Auth Token (Simple check)
    token = data.get("auth_token")
    if token != "secret-token-123": # Hardcoded for demo
        return jsonify({"error": "Invalid authentication token"}), 401
        
    config["datasource_type"] = data.get("datasource_type", "loki")
    config["datasource"] = data.get("datasource")
    
    # Update dynamic URLs
    if data.get("loki_url"):
        config["loki_url"] = data.get("loki_url")
    if data.get("otel_url"):
        config["otel_url"] = data.get("otel_url")
    
    # Update Generic AI Config
    if data.get("ai_api_key"):
        config["ai_api_key"] = data.get("ai_api_key")
    if data.get("ai_api_url"):
        config["ai_api_url"] = data.get("ai_api_url")
    if data.get("ai_model"):
        config["ai_model"] = data.get("ai_model")
    
    if config["datasource_type"] == "s3":
        config["aws_region"] = data.get("aws_region", "us-east-1")
        config["s3_prefix"] = data.get("s3_prefix", "logs/")
        config["insights_bucket"] = data.get("insights_bucket")
        # NOTE: No longer accepting aws_access_key/secret_key for security
    
    print(f"Config updated: Datasource set to {config['datasource']} ({config['datasource_type']})", flush=True)
    return jsonify({"status": "success", "config": {k:v for k,v in config.items() if not any(s in k.lower() for s in ["secret", "key", "token"])}})
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "config": {k:v for k,v in config.items() if not any(s in k.lower() for s in ["secret", "key", "token"])}})
def get_recent_logs_from_storage(limit=100):
    """Fallback to fetch recent logs from storage when Loki is unavailable"""
    logs = []
    try:
        print("DEBUG: Fetching recent logs from storage...", flush=True)
        now = datetime.now()
        from datetime import timedelta
        # Check last 2 hours
        hours_to_check = [now, now - timedelta(hours=1)]
        
        log_files = []
        if hasattr(storage_backend, 's3'):
            # S3 Discovery
            try:
                # We need to find where the logs are. 
                # Assuming standard structure: logs/<env>/<service>/YYYY/MM/DD/HH/
                resp = storage_backend.s3.list_objects_v2(Bucket=storage_backend.bucket, Prefix="logs/", Delimiter="/")
                envs = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
                
                for env in envs:
                    resp = storage_backend.s3.list_objects_v2(Bucket=storage_backend.bucket, Prefix=env, Delimiter="/")
                    services = [p['Prefix'] for p in resp.get('CommonPrefixes', [])]
                    
                    for service in services:
                        for h in hours_to_check:
                            path = f"{service}{h.strftime('%Y/%m/%d/%H')}/"
                            files = storage_backend.list_files(path)
                            log_files.extend(files)
            except Exception as e:
                print(f"S3 Discovery Error: {e}", flush=True)
        else:
            # Local Storage
            log_files = storage_backend.list_files("logs/")
        # Sort files (newest last) and take recent ones
        log_files.sort(reverse=True) 
        
        print(f"DEBUG: Found {len(log_files)} recent log files. Reading top 5...", flush=True)
        for f in log_files[:5]: # Check top 5 most recent files only
            content = storage_backend.read_file(f)
            if not content: continue
            
            file_logs = []
            try:
                data = json.loads(content)
                file_logs = data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                for line in content.splitlines():
                    if line.strip():
                        try:
                            file_logs.append(json.loads(line))
                        except:
                            file_logs.append({"message": line})
            
            # Add to logs
            logs.extend(file_logs)
            if len(logs) >= limit:
                break
                
    except Exception as e:
        print(f"Error fetching logs from storage: {e}", flush=True)
        
    return logs[:limit]
@app.route('/query', methods=['POST'])
def query_ai():
    try:
        print("DEBUG: Received /query request", flush=True)
        data = request.json
        user_query = data.get('query')
        if not user_query:
            return jsonify({"error": "Query is required"}), 400
        # Fetch recent logs for context
        context_query = '{exporter="OTLP"}'
        start_time = int((time.time() - 600) * 1000000000) # Last 10 mins
        
        params = {
            'query': context_query,
            'start': str(start_time),
            'limit': '100'
        }
        
        logs_context = ""
        loki_success = False
        
        try:
            loki_url = config.get("loki_url", "http://loki:3100")
            if loki_url.endswith('/'):
                loki_url = loki_url[:-1]
                
            print(f"DEBUG: Querying Loki at {loki_url}...", flush=True)
            loki_resp = requests.get(f"{loki_url}/loki/api/v1/query_range", params=params, timeout=2)
            if loki_resp.status_code == 200:
                loki_data = loki_resp.json()
                if 'data' in loki_data and 'result' in loki_data['data']:
                    results = loki_data['data']['result']
                    if results:
                        loki_success = True
                        print(f"DEBUG: Found {len(results)} streams in Loki", flush=True)
                        for stream in results:
                            for value in stream['values']:
                                logs_context += f"{value[1]}\n"
        except Exception as e:
            print(f"Error fetching context from Loki: {e}", flush=True)
        # Fallback to Storage if Loki failed or returned no logs
        if not loki_success or not logs_context.strip():
            print("DEBUG: Loki context empty, using fallback storage...", flush=True)
            recent_logs = get_recent_logs_from_storage(limit=50)
            for log in recent_logs:
                msg = log.get("message", "") or str(log)
                logs_context += f"{msg}\n"
                
        print(f"DEBUG: Context length: {len(logs_context)} chars", flush=True)
        api_key = config.get("ai_api_key")
        api_url = config.get("ai_api_url", DEFAULT_AI_API_URL)
        model = config.get("ai_model", DEFAULT_AI_MODEL)
        if not api_key:
            return jsonify({"error": "AI API Key not configured"}), 500
        prompt = f"""
        You are an AI SRE assistant. Use the following logs context to answer the user's question.
        
        Logs Context (Last 10 mins):
        {logs_context[:4000]} # Truncate to avoid token limits
        
        User Question: {user_query}
        
        Provide a helpful, technical, and concise answer. 
        Use Markdown formatting for better readability:
        - Use double newlines between paragraphs and list items.
        - Use bold text for key terms and status indicators.
        - Use bullet points for lists.
        - Use code blocks for technical logs or commands.
        """
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a technical SRE assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3
            }
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            if "openrouter" in api_url:
                headers["HTTP-Referer"] = "http://localhost:8080"
                headers["X-Title"] = "AI Log Analyzer"
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                print(f"DEBUG: Calling AI API (Attempt {attempt + 1})...", flush=True)
                response = requests.post(
                    url=api_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result['choices'][0]['message']['content'].strip()
                    print("DEBUG: AI Response received", flush=True)
                    return jsonify({"answer": answer})
                
                print(f"DEBUG: AI API Error: {response.status_code} {response.text}", flush=True)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        print(f"DEBUG: Rate limit hit, retrying in {retry_delay}s...", flush=True)
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    return jsonify({"answer": "⚠️ **Rate Limit Exceeded**: I'm currently receiving too many requests. Since I'm using a free AI model, please wait a moment before asking another question. \n\n**Tip**: You can increase your OpenRouter limits by adding a small amount of credit ($5) to your account."}), 200
                
                return jsonify({"error": f"AI API returned {response.status_code}: {response.text}"}), 500
            
        except Exception as e:
            print(f"Error querying AI: {e}", flush=True)
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"ERROR in /query endpoint: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
if __name__ == "__main__":
    # Test generalize_message
    print("DEBUG: Testing generalize_message...", flush=True)
    msg = "Invalid coupon code: SAVE46"
    gen, det = generalize_message(msg)
    print(f"DEBUG: Test 1: '{msg}' -> '{gen}', details: {det}", flush=True)
    
    msg = "Account locked for user_123 due to failed attempts"
    gen, det = generalize_message(msg)
    print(f"DEBUG: Test 2: '{msg}' -> '{gen}', details: {det}", flush=True)
    # Start analysis loop in background thread
    thread = threading.Thread(target=analysis_loop, daemon=True)
    thread.start()
    
    # Start Flask API
    app.run(host="0.0.0.0", port=5000)