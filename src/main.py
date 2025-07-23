# main.py

import json
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from confluent_kafka import Producer, Consumer, KafkaException

from src.core.config import KAFKA_BROKER, TOPIC_NAME, MODE
from src.api.endpoints import router as api_router # 분리된 라우터를 import

# --- Kafka Consumer (main.py에 유지 또는 별도 파일로 분리 가능) ---
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
    title="Confluent Kafka FastAPI Example (Refactored)",
    description="A refactored FastAPI application with separated concerns."
)

# --- 라우터 포함 ---
app.include_router(api_router)

# --- 메인 실행 ---
if __name__ == '__main__':
    uvicorn.run(
        "main:app", 
        host='0.0.0.0', 
        port=5001, 
        reload=(MODE != "kubernetes")
    )
