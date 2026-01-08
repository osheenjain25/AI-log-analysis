import time
import os
import random
import logging
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

import json
import boto3
from datetime import datetime
import threading

# Setup OpenTelemetry Logging
resource = Resource.create({"service.name": "log-generator"})
logger_provider = LoggerProvider(resource=resource)
set_logger_provider(logger_provider)

exporter = OTLPLogExporter(endpoint="http://otel-collector:4317", insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

class S3LogHandler(logging.Handler):
    def __init__(self, bucket, region="us-east-1"):
        super().__init__()
        self.bucket = bucket
        self.s3 = boto3.client('s3', region_name=region)
        self.buffer = []
        self.lock = threading.RLock() # Use RLock to prevent deadlocks
        self.last_upload = time.time()
        self.upload_interval = 30 # Upload every 30 seconds
        self.service_name = os.getenv("SERVICE_NAME", "log-generator")
        self.environment = os.getenv("ENVIRONMENT", "production")

    def emit(self, record):
        try:
            # print(f"DEBUG: S3LogHandler emit called for: {record.getMessage()}", flush=True)
            log_data = {
                "timestamp": int(record.created * 1000000000),
                "severity": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "attributes": {
                    **getattr(record, "extra", {}),
                    "service_name": self.service_name,
                    "environment": self.environment
                }
            }
            with self.lock:
                self.buffer.append(log_data)
            
            if time.time() - self.last_upload > self.upload_interval:
                self.flush()
        except Exception as e:
            print(f"DEBUG: S3LogHandler emit error: {e}", flush=True)
            self.handleError(record)

    def flush(self):
        with self.lock:
            if not self.buffer:
                return
            logs_to_upload = self.buffer[:]
            self.buffer = []
            self.last_upload = time.time()

        try:
            timestamp = int(time.time())
            now = datetime.now()
            # New path structure: logs/{environment}/{service_name}/{YYYY}/{MM}/{DD}/{HH}/logs_{timestamp}.json
            key = f"logs/{self.environment}/{self.service_name}/{now.strftime('%Y/%m/%d/%H')}/logs_{timestamp}.json"
            
            content = ""
            for log in logs_to_upload:
                content += json.dumps(log) + "\n"
                
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType='application/json'
            )
            print(f"Uploaded {len(logs_to_upload)} logs to s3://{self.bucket}/{key}", flush=True)
        except Exception as e:
            print(f"Error uploading logs to S3: {e}", flush=True)

class LocalLogHandler(logging.Handler):
    def __init__(self, log_dir="/app/logs"):
        super().__init__()
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.buffer = []
        self.lock = threading.RLock()
        self.last_upload = time.time()
        self.upload_interval = 10 # Faster for local testing
        self.service_name = os.getenv("SERVICE_NAME", "log-generator")
        self.environment = os.getenv("ENVIRONMENT", "production")

    def emit(self, record):
        try:
            log_data = {
                "timestamp": int(record.created * 1000000000),
                "severity": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "attributes": {
                    **getattr(record, "extra", {}),
                    "service_name": self.service_name,
                    "environment": self.environment
                }
            }
            with self.lock:
                self.buffer.append(log_data)
            
            if time.time() - self.last_upload > self.upload_interval:
                self.flush()
        except Exception as e:
            print(f"DEBUG: LocalLogHandler emit error: {e}", flush=True)
            self.handleError(record)

    def flush(self):
        with self.lock:
            if not self.buffer:
                return
            logs_to_upload = self.buffer[:]
            self.buffer = []
            self.last_upload = time.time()

        try:
            timestamp = int(time.time())
            now = datetime.now()
            # Match S3 path structure: logs/{environment}/{service_name}/{YYYY}/{MM}/{DD}/{HH}/logs_{timestamp}.json
            rel_path = f"logs/{self.environment}/{self.service_name}/{now.strftime('%Y/%m/%d/%H')}"
            full_dir = os.path.join(self.log_dir, rel_path)
            os.makedirs(full_dir, exist_ok=True)
            
            filename = f"logs_{timestamp}.json"
            full_path = os.path.join(full_dir, filename)
            
            content = ""
            for log in logs_to_upload:
                content += json.dumps(log) + "\n"
                
            with open(full_path, 'w') as f:
                f.write(content)
            print(f"Saved {len(logs_to_upload)} logs to {full_path}", flush=True)
        except Exception as e:
            print(f"Error saving logs locally: {e}", flush=True)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Attach handlers
datasource_type = os.getenv("DATASOURCE_TYPE", "s3")
s3_bucket = os.getenv("AWS_S3_LOGS_BUCKET")

if datasource_type == "local":
    print("Local Archiving enabled (DATASOURCE_TYPE=local)", flush=True)
    local_handler = LocalLogHandler("/app/logs")
    logging.getLogger().addHandler(local_handler)
elif s3_bucket:
    print(f"S3 Archiving enabled for bucket: {s3_bucket}", flush=True)
    s3_handler = S3LogHandler(s3_bucket)
    logging.getLogger().addHandler(s3_handler)
else:
    print("Archiving disabled (Neither S3 bucket nor Local datasource set)", flush=True)

# handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
# logging.getLogger().addHandler(handler)
# StreamHandler is already added by basicConfig

class EcommerceService:
    def __init__(self):
        service_name = os.getenv("SERVICE_NAME", "ecommerce_service")
        self.logger = logging.getLogger(service_name)
        self.products = ["laptop", "phone", "headphones", "monitor", "keyboard", "mouse", "tablet", "camera"]
        self.error_scenarios = [
            "timeout", "inventory", "payment", "database", "network", 
            "authentication", "rate_limit", "cache", "validation"
        ]

    def login(self, user_id):
        self.logger.debug(f"Login attempt for user_{user_id}", extra={"user_id": user_id})
        
        # Simulate various login scenarios
        scenario = random.random()
        if scenario < 0.6:  # 60% success
            self.logger.info(f"User_{user_id} logged in successfully", extra={"user_id": user_id, "event": "login_success"})
        elif scenario < 0.75:  # 15% invalid password
            self.logger.warning(f"Invalid password for user_{user_id}", extra={"user_id": user_id, "event": "login_failed"})
        elif scenario < 0.85:  # 10% account locked
            self.logger.error(f"Account locked for user_{user_id} due to multiple failed attempts", extra={"user_id": user_id, "event": "account_locked"})
        elif scenario < 0.92:  # 7% MFA timeout
            self.logger.error(f"MFA verification timeout for user_{user_id}", extra={"user_id": user_id, "error_type": "mfa_timeout"})
        elif scenario < 0.97:  # 5% suspicious activity
            self.logger.critical(f"Suspicious activity detected for user_{user_id}. Account flagged.", extra={"user_id": user_id, "error_type": "security_alert"})
        else:  # 3% authentication service down
            self.logger.critical(f"Authentication service unavailable for user_{user_id}", extra={"user_id": user_id, "event": "auth_service_down"})



    def search_product(self, query):
        self.logger.debug(f"Searching for product: {query}", extra={"query": query})
        
        scenario = random.random()
        if scenario < 0.7:  # 70% success
            results = random.randint(1, 50)
            self.logger.info(f"Found {results} results for {query}", extra={"query": query})
        elif scenario < 0.8:  # 10% timeout
            self.logger.error(f"Search service timeout for query: {query}", extra={"query": query, "error_type": "timeout"})
        elif scenario < 0.85:  # 5% slow query
            self.logger.warning(f"Slow query detected for: {query}", extra={"query": query, "latency_ms": random.randint(2000, 5000)})
        elif scenario < 0.9:  # 5% no results
            self.logger.warning(f"No results found for query: {query}", extra={"query": query})
        elif scenario < 0.95:  # 5% cluster unhealthy
            self.logger.critical(f"Elasticsearch cluster status: RED. Nodes failing.", extra={"error_type": "cluster_unhealthy"})
        else:  # 5% search index error
            self.logger.critical(f"Search index corruption detected for query: {query}", extra={"query": query, "error_type": "index_corruption"})

    def checkout(self, user_id, amount):
        self.logger.info(f"Processing checkout for user_{user_id}, total: ${amount}", extra={"user_id": user_id, "amount": amount})
        
        scenario = random.random()
        if scenario < 0.5:  # 50% success
            order_id = random.randint(10000, 99999)
            self.logger.info(f"Order placed successfully for user_{user_id}", extra={"user_id": user_id, "order_id": order_id})
        elif scenario < 0.65:  # 15% inventory issue
            self.logger.error(f"Inventory check failed: Item out of stock", extra={"user_id": user_id, "error_type": "inventory"})
        elif scenario < 0.75:  # 10% payment gateway failure
            self.logger.critical(f"Payment gateway connection failed", extra={"user_id": user_id, "amount": amount, "error_type": "payment_gateway"})
        elif scenario < 0.82:  # 7% database error
            self.logger.error(f"Database connection lost during checkout", extra={"user_id": user_id, "error_type": "database"})
        elif scenario < 0.88:  # 6% tax service down
            self.logger.error(f"Tax calculation service unavailable", extra={"user_id": user_id, "error_type": "tax_service"})
        elif scenario < 0.94:  # 6% shipping error
            self.logger.error(f"Shipping calculator failed to respond", extra={"user_id": user_id, "error_type": "shipping_service"})
        else:  # 6% validation error
            self.logger.error(f"Payment validation failed: Invalid card details", extra={"user_id": user_id, "error_type": "validation"})

    def add_to_cart(self, user_id, product):
        scenario = random.random()
        if scenario < 0.8:  # 80% success
            self.logger.info(f"User_{user_id} added {product} to cart", extra={"user_id": user_id, "product": product})
        elif scenario < 0.9:  # 10% cache error
            self.logger.error(f"Cache service unavailable, cart update failed", extra={"user_id": user_id, "error_type": "cache"})
        elif scenario < 0.95:  # 5% capacity limit
             self.logger.warning(f"Cart capacity reached for user_{user_id}", extra={"user_id": user_id, "error_type": "capacity_limit"})
        else:  # 5% rate limit
            self.logger.warning(f"Rate limit exceeded for user_{user_id}", extra={"user_id": user_id, "error_type": "rate_limit"})

    def view_product(self, user_id, product):
        scenario = random.random()
        if scenario < 0.9:  # 90% success
            self.logger.info(f"User_{user_id} viewed product: {product}", extra={"user_id": user_id, "product": product})
        else:  # 10% network error
            self.logger.error(f"Network timeout while loading product details", extra={"user_id": user_id, "product": product, "error_type": "network"})

    def apply_coupon(self, user_id, coupon_code):
        scenario = random.random()
        if scenario < 0.6:  # 60% valid
            discount = random.randint(5, 30)
            self.logger.info(f"Coupon {coupon_code} applied: {discount}% discount", extra={"user_id": user_id, "coupon": coupon_code, "discount": discount})
        elif scenario < 0.85:  # 25% expired
            self.logger.warning(f"Coupon {coupon_code} has expired", extra={"user_id": user_id, "coupon": coupon_code})
        else:  # 15% invalid
            self.logger.error(f"Invalid coupon code: {coupon_code}", extra={"user_id": user_id, "coupon": coupon_code, "error_type": "validation"})

    def update_profile(self, user_id):
        scenario = random.random()
        if scenario < 0.85:
            self.logger.info(f"User_{user_id} updated profile successfully", extra={"user_id": user_id})
        elif scenario < 0.92:
            self.logger.error(f"Failed to update profile for user_{user_id}: Invalid email format", extra={"user_id": user_id, "error_type": "validation"})
        elif scenario < 0.97:
            self.logger.error(f"Database lock timeout while updating user_{user_id} profile", extra={"user_id": user_id, "error_type": "database_lock"})
        else:
            self.logger.error(f"Avatar upload failed for user_{user_id}: Storage quota exceeded", extra={"user_id": user_id, "error_type": "storage_full"})

    def track_order(self, user_id):
        scenario = random.random()
        if scenario < 0.8:
            self.logger.info(f"Order tracking info retrieved for user_{user_id}", extra={"user_id": user_id})
        elif scenario < 0.95:
            self.logger.warning(f"Order not found for tracking request from user_{user_id}", extra={"user_id": user_id})
        else:
            self.logger.critical(f"Third-party tracking API is down", extra={"error_type": "dependency_failure"})

    def request_refund(self, user_id):
        scenario = random.random()
        if scenario < 0.7:
            self.logger.info(f"Refund request submitted for user_{user_id}", extra={"user_id": user_id})
        elif scenario < 0.9:
            self.logger.error(f"Refund request denied for user_{user_id}: Policy violation", extra={"user_id": user_id, "error_type": "policy_violation"})
        else:
            self.logger.critical(f"Bank API timeout during refund processing for user_{user_id}", extra={"user_id": user_id, "error_type": "bank_api_timeout"})

    def trigger_random_anomaly(self):
        anomaly = random.choice([
            "Global DNS resolution failure",
            "Region us-east-1 availability zone outage",
            "API Key revoked for external payment provider",
            "Internal backbone network congestion",
            "Root certificate expiration detected"
        ])
        self.logger.critical(f"SYSTEM ANOMALY: {anomaly}", extra={"error_type": "system_outage", "is_anomaly": True})

    def run_simulation(self):
        print("DEBUG: Starting simulation loop...", flush=True)
        while True:
            user_id = random.randint(1, 100)
            action = random.choice([
                "login", "search", "checkout", "add_to_cart", 
                "view_product", "apply_coupon", "update_profile",
                "track_order", "request_refund", "anomaly"
            ])
            
            if action == "login":
                self.login(user_id)
            elif action == "search":
                self.search_product(random.choice(self.products))
            elif action == "checkout":
                self.checkout(user_id, random.randint(50, 2000))
            elif action == "add_to_cart":
                self.add_to_cart(user_id, random.choice(self.products))
            elif action == "view_product":
                self.view_product(user_id, random.choice(self.products))
            elif action == "apply_coupon":
                coupon = f"SAVE{random.randint(10, 50)}"
                self.apply_coupon(user_id, coupon)
            elif action == "update_profile":
                self.update_profile(user_id)
            elif action == "track_order":
                self.track_order(user_id)
            elif action == "request_refund":
                self.request_refund(user_id)
            elif action == "anomaly":
                if random.random() < 0.1: # Only 10% chance when "anomaly" is picked
                    self.trigger_random_anomaly()
            
            time.sleep(random.uniform(0.1, 0.8)) # Slightly faster for more logs

if __name__ == "__main__":
    print("Starting E-commerce Service Simulation...", flush=True)
    service = EcommerceService()
    service.run_simulation()
