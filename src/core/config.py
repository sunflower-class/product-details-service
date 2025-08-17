import os

# --- Kafka & App 설정 ---
MODE = os.environ.get("MODE", "development")
TOPIC_NAME = 'fastapi-confluent-topic'

# 환경(mode)에 따른 Kafka 브로커 주소 설정
if MODE == "docker":
    KAFKA_BROKER = 'kafka:9092'
elif MODE == "kubernetes":
    KAFKA_BROKER = 'kafka-svc:9092'
else:
    KAFKA_BROKER = 'localhost:9092'

print(f"Running in {MODE} mode...")
if MODE != "development":
    print(f"Kafka Broker is set to {KAFKA_BROKER}")

# --- Redis 설정 (Azure Redis Cache 지원) ---
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

# Redis 환경별 설정 (Azure Redis를 사용하지 않는 경우)
if not REDIS_PASSWORD and MODE == "docker":
    REDIS_HOST = 'redis'
elif not REDIS_PASSWORD and MODE == "kubernetes":
    REDIS_HOST = 'redis-svc'

print(f"Redis Host is set to {REDIS_HOST}:{REDIS_PORT} (SSL: {REDIS_SSL})")

# settings 객체 (Worker와 호환성을 위해)
class Settings:
    MODE = MODE
    KAFKA_BROKER = KAFKA_BROKER
    TOPIC_NAME = TOPIC_NAME
    REDIS_HOST = REDIS_HOST
    REDIS_PORT = REDIS_PORT
    REDIS_DB = REDIS_DB
    REDIS_PASSWORD = REDIS_PASSWORD
    REDIS_SSL = REDIS_SSL

settings = Settings()
