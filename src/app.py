import os
import json
import threading
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from confluent_kafka import Producer, Consumer, KafkaException

# --- 설정 (변경 없음) ---
KAFKA_BROKER = 'localhost:9092'
TOPIC_NAME = 'fastapi-confluent-topic'
MODE = os.environ.get("MODE", "development")

print(f"Running in {MODE} mode...")

if MODE == "docker":
    KAFKA_BROKER = 'kafka:9092'
elif MODE == "kubernetes":
    KAFKA_BROKER = 'kafka-svc:9092'

if MODE != "development":
    print(f"Kafka Broker is set to {KAFKA_BROKER}")

# --- Kafka Consumer ---
def consume_messages():
    conf = {
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'fastapi-consumer-group',
        'auto.offset.reset': 'latest'
    }
    consumer = Consumer(conf)
    try:
        consumer.subscribe([TOPIC_NAME])
        print(f"Consumer started on topic '{TOPIC_NAME}'...")
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaException._PARTITION_EOF:
                    continue
                else:
                    print(f"Consumer error: {msg.error()}")
                    break
            try:
                received_data = json.loads(msg.value().decode('utf-8'))
                print(f"Received message: {received_data}")
            except json.JSONDecodeError:
                print(f"Could not decode message: {msg.value()}")
    except Exception as e:
        print(f"Error in consumer thread: {e}")
    finally:
        print("Consumer closing...")
        consumer.close()


# --- Lifespan 이벤트 핸들러 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... (기존 코드와 동일) ...
    if MODE != "development":
        print("Connecting to Kafka...")
        try:
            producer_conf = {'bootstrap.servers': KAFKA_BROKER}
            app.state.producer = Producer(producer_conf)
            print("Kafka Producer connected successfully.")
        except Exception as e:
            print(f"Error creating producer: {e}")
            app.state.producer = None
        
        consumer_thread = threading.Thread(target=consume_messages, daemon=True)
        consumer_thread.start()
        print("Kafka Consumer thread started.")
    else:
        print("Running in development mode without Kafka connection.")
        app.state.producer = None

    yield

    if MODE != "development" and app.state.producer:
        print("Application shutdown: Flushing final messages...")
        app.state.producer.flush()
        print("Producer flushed.")
    else:
        print("Application shutdown.")

# --- FastAPI 앱 생성 ---
app = FastAPI(
    lifespan=lifespan,
    title="Confluent Kafka FastAPI Example",
    description="FastAPI application using the confluent-kafka library and lifespan events."
)

# --- Kafka 전송 로직을 처리하는 헬퍼 함수 ---
def handle_kafka_production(producer: Optional[Producer], data: Dict[str, Any]):
    """
    모드에 따라 Kafka 메시지 전송 또는 로깅을 처리하는 중앙 함수.
    운영 모드에서 Producer가 없으면 예외를 발생시킵니다.
    """
    if MODE == "development":
        # 개발 모드에서는 로깅만 하고 종료
        print(f"DEV MODE: Received message, not sending to Kafka: {data}")
        return {"status": "Message accepted for processing", "data": data}

    # 운영 모드(docker, kubernetes 등) 로직
    if not producer:
        # Producer가 준비되지 않았으면 명시적인 에러 발생
        raise HTTPException(status_code=503, detail="Kafka Producer is not available.")
    
    try:
        producer.produce(
            TOPIC_NAME,
            value=json.dumps(data).encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
        print(f"Message sent to Kafka topic '{TOPIC_NAME}': {data}")
        return {"status": "Message accepted for processing", "data": data}
    except Exception as e:
        # Kafka 전송 중 다른 에러가 발생하면 그대로 전달
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

def delivery_report(err, msg):
    """ 메시지 전송 결과를 비동기적으로 처리하는 콜백 함수 """
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

# --- API 엔드포인트 ---

@app.get('/python')
def running_test():
    return "python API is running!"

@app.post("/python/message", status_code=202)
async def send_message(message_data: Dict[str, Any], request: Request):
    # 모드에 따른 분기 처리를 헬퍼 함수에 위임
    return handle_kafka_production(request.app.state.producer, message_data)

@app.get("/actuator/health", include_in_schema=False)
async def health_check(request: Request):
    if MODE == "development":
        return {"status": "OK", "detail": "Running in development mode"}
    
    if not request.app.state.producer:
         raise HTTPException(status_code=503, detail="Producer is not available")
    return {"status": "OK"}


# --- 메인 실행 (미사용) ---
if __name__ == '__main__':
    uvicorn.run(
        "main:app", 
        host='0.0.0.0', 
        port=5001, 
        reload=(MODE != "kubernetes")
    )
