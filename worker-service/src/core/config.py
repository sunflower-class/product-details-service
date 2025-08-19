import os

# Worker 서비스 설정 (Kafka 불필요, 인증 불필요)
MODE = os.environ.get("MODE", "development")

# --- Redis 설정 (Azure Redis Cache) ---
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"
REDIS_DB = int(os.environ.get("REDIS_DB", 0))

# --- Product Service 설정 (더 이상 사용 안함 - 내부 DB 사용) ---
# PRODUCT_SERVICE_URL = os.environ.get("PRODUCT_SERVICE_URL", "http://localhost:8001")

# --- AWS S3 설정 ---
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# --- AI API Keys ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")

# --- Database ---
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- Worker 설정 ---
WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", 1))
TASK_TIMEOUT = int(os.environ.get("TASK_TIMEOUT", 300))  # 5분

print(f"Worker Service Configuration:")
print(f"  Mode: {MODE}")
print(f"  Redis: {REDIS_HOST}:{REDIS_PORT} (SSL: {REDIS_SSL})")
# print(f"  Product Service: {PRODUCT_SERVICE_URL}")  # 더 이상 외부 Product 서비스 사용 안함
print(f"  S3 Bucket: {S3_BUCKET_NAME}")
print(f"  Worker Concurrency: {WORKER_CONCURRENCY}")

# settings 객체 (호환성 유지)
class Settings:
    MODE = MODE
    REDIS_HOST = REDIS_HOST
    REDIS_PORT = REDIS_PORT
    REDIS_PASSWORD = REDIS_PASSWORD
    REDIS_SSL = REDIS_SSL
    REDIS_DB = REDIS_DB
    # PRODUCT_SERVICE_URL = PRODUCT_SERVICE_URL  # 더 이상 사용 안함
    DATABASE_URL = DATABASE_URL

settings = Settings()
