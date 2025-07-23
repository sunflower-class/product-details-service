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
