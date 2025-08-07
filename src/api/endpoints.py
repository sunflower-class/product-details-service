from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException
from typing import List
from pydantic import BaseModel

from src.services.kafka_service import handle_kafka_production
from src.services.create_html import product_to_html
from src.services.create_image import create_image, reshape_image, download_image

from src.core.config import MODE

# APIRouter 인스턴스 생성
router = APIRouter(prefix="/api/generation")

@router.get('/')
def running_test():
    """API 테스트용 엔드포인트"""
    return "python API is running!"

@router.post("/message", status_code=202)
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

class ProductInfo(BaseModel):
    product_data: str
    product_image_url: str

class HtmlElementsResponse(BaseModel):
    html_list: List[str]

class ApiResponse(BaseModel):
    status: str
    data: HtmlElementsResponse    

@router.post("/display-list", 
             response_model=ApiResponse,
             tags=["Products"])
async def generate_html_codes(info: ProductInfo, request: Request):
    """상품 정보를 받아 html 코드를 생성하여 반환하는 엔드포인트"""
    html_list = product_to_html(info.product_data.strip(), info.product_image_url.strip())
    producer = request.app.state.producer
    return handle_kafka_production(producer, { "html_list": html_list })

class ImageInfo(BaseModel):
    prompt_data: str
    image_url: str

class ImageResponse(BaseModel):
    image_url: str

class ImageApiResponse(BaseModel):
    status: str
    data: ImageResponse    

@router.post("/image", 
             response_model=ImageApiResponse,
             tags=["Images"])
async def generate_image(info: ImageInfo, request: Request):
    """이미지 주소를 받아 프롬프트대로 수정하여 새로운 이미지 주소를 반환하는 엔드포인트"""
    res = reshape_image(info.prompt_data.strip(), info.image_url.strip())

    producer = request.app.state.producer
    return handle_kafka_production(producer, { "image_url": res.data[0].url })

