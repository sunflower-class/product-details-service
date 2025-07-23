from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException

from src.services.kafka_service import handle_kafka_production
from src.core.config import MODE

# APIRouter 인스턴스 생성
router = APIRouter()

@router.get('/python')
def running_test():
    """API 테스트용 엔드포인트"""
    return "python API is running!"

@router.post("/python/message", status_code=202)
async def send_message(message_data: Dict[str, Any], request: Request):
    """Kafka로 메시지를 전송하는 엔드포인트"""
    producer = request.app.state.producer
    return handle_kafka_production(producer, message_data)

@router.get("/actuator/health", include_in_schema=False)
async def health_check(request: Request):
    """애플리케이션 상태 확인 엔드포인트"""
    if MODE == "development":
        return {"status": "OK", "detail": "Running in development mode"}
    
    if not request.app.state.producer:
        raise HTTPException(status_code=503, detail="Producer is not available")
        
    return {"status": "OK"}
