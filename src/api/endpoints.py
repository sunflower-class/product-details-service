import os
import uuid
import shutil

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import List
from pydantic import BaseModel

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.staticfiles import StaticFiles

from src.services.kafka_service import handle_kafka_production
from src.services.create_image import create_image, reshape_image, download_image
from src.core.config import MODE
from src.core.auth import get_user_id, get_optional_user_id

STATIC_DIR = "static/images"

# APIRouter 인스턴스 생성
router = APIRouter(prefix="/api/generation")

@router.get("/actuator/health", include_in_schema=False)
async def health_check(request: Request):
    """애플리케이션 상태 확인 엔드포인트 (X-User-Id 불필요)"""
    if MODE == "development":
        return {"status": "OK", "detail": "Running in development mode"}
    
    if not request.app.state.producer:
        raise HTTPException(status_code=503, detail="Producer is not available")
        
    return {"status": "OK"}

@router.post("/message", status_code=202)
async def send_message(message_data: Dict[str, Any], request: Request):
    """Kafka로 메시지를 전송하는 엔드포인트"""
    producer = request.app.state.producer
    return handle_kafka_production(producer, message_data)

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
async def generate_html_codes(
    info: ProductInfo, 
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """상품 정보를 받아 전체 플로우로 HTML 코드를 생성하여 반환하는 엔드포인트"""
    from src.services.html_generation_flow import html_flow
    
    print(f"📝 사용자 {user_id}가 HTML 생성 요청 (전체 플로우)")
    
    # 전체 HTML 생성 플로우 실행
    result = await html_flow.generate_complete_html(
        product_data=info.product_data.strip(),
        product_image_url=info.product_image_url.strip(),
        user_id=user_id,
        user_session=request.headers.get("X-Session-Id")  # 선택적 세션 ID
    )
    
    producer = request.app.state.producer
    
    if result["success"]:
        print(f"✅ HTML 생성 완료 - ProductDetails ID: {result['product_details_id']}")
        return handle_kafka_production(producer, { 
            "html_list": result["html_list"],
            "product_details_id": result["product_details_id"],
            "product_id": result.get("product_id"),
            "image_count": result["image_count"]
        })
    else:
        print(f"⚠️ HTML 생성 실패, 폴백 사용: {result.get('error')}")
        return handle_kafka_production(producer, { 
            "html_list": result.get("fallback_html", ["<div>생성 실패</div>"])
        })

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
async def generate_image(
    info: ImageInfo, 
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """이미지 주소를 받아 프롬프트대로 수정하여 새로운 이미지 주소를 반환하는 엔드포인트"""
    res = reshape_image(info.prompt_data.strip(), info.image_url.strip())

    producer = request.app.state.producer
    print(f"📝 사용자 {user_id}가 이미지 생성 요청")
    
    return handle_kafka_production(producer, { "image_url": res.data[0].url })

@router.post("/upload-image", tags=["Images"])
async def upload_image(
    url: str, 
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """
    이미지 파일을 직접 업로드받아 서버에 저장하고,
    저장된 이미지의 URL을 반환합니다.
    """
    try:
        filepath = download_image(url=url, path=STATIC_DIR, ext=None)

        # 서버에서 접근 가능한 URL 생성
        # request.base_url은 'http://127.0.0.1:8000/' 같은 서버의 기본 주소를 나타냅니다.
        server_url = str(request.base_url)
        print(server_url, filepath)
        saved_url = f"{server_url}{filepath}"
        
        print(f"✅ 사용자 {user_id} - 파일 저장 완료: {filepath}")
        print(f"🔗 제공 URL: {saved_url}")
        
        return {"filepath": filepath, "saved_url": saved_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류 발생: {str(e)}")
    