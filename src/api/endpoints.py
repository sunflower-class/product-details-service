import os
import uuid
import shutil

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.staticfiles import StaticFiles

from src.services.kafka_service import handle_kafka_production
from src.services.create_image import create_image, reshape_image, download_image
from src.core.config import MODE
from src.core.auth import get_user_id, get_optional_user_id
from src.models.models_simple import ProductDetails, ProductImage, simple_db

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
    product_image_url: Optional[str] = None  # 선택사항으로 변경
    user_id: Optional[str] = None
    features: Optional[List[str]] = None
    target_customer: Optional[str] = None
    tone: Optional[str] = None
    
    class Config:
        extra = "ignore"  # 정의되지 않은 추가 필드는 무시

class HtmlElementsResponse(BaseModel):
    html_list: List[str]

class ApiResponse(BaseModel):
    status: str
    data: HtmlElementsResponse
    task_id: Optional[str] = None

class ProductDetailsUpdate(BaseModel):
    product_id: Optional[int] = None
    original_product_info: Optional[str] = None
    generated_html: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # 'draft', 'published', 'archived'
    
    class Config:
        extra = "ignore"

class ProductDetailsResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None    

@router.post("/display-list", 
             response_model=ApiResponse,
             status_code=202,
             tags=["Products"])
async def generate_html_codes(
    info: ProductInfo, 
    request: Request,
    user_id: str = Depends(get_user_id)
):
    """상품 정보를 받아 Worker 서비스로 비동기 처리를 요청하는 엔드포인트"""
    from src.services.task_manager import task_manager
    
    print(f"📝 사용자 {user_id} HTML 생성 요청")
    
    # 1. 먼저 Product를 생성
    from src.services.product_service import ProductService
    
    producer = request.app.state.producer
    
    try:
        # 이미지 URL이 없으면 기본 플레이스홀더 사용 (DNS 이슈 방지)
        image_url = info.product_image_url.strip() if info.product_image_url else "https://placehold.co/400x300/png?text=Product+Image"
        
        # Product 데이터 파싱 및 생성
        product_create_data = {
            'name': info.product_data.split('\n')[0] if info.product_data else "상품명 없음",  # 첫 줄을 상품명으로
            'description': info.product_data.strip(),
            'original_product_data': info.product_data.strip(),
            'main_image_url': image_url,
            'features': info.features,
            'target_customer': info.target_customer,
            'tone': info.tone,
            'status': 'active'
        }
        
        product = ProductService.create_product(
            product_data=product_create_data,
            user_id=user_id,
            user_session=request.headers.get("X-Session-Id")
        )
        
        if not product:
            raise Exception("Product 생성 실패")
        
        print(f"✅ Product 생성 완료 - ID: {product.id}")
        
        # 2. Redis 큐에 작업 제출 (Worker 서비스가 처리)
        result = task_manager.submit_task(
            product_data=info.product_data.strip(),
            product_image_url=image_url,
            user_id=user_id,
            product_id=product.id,  # Product ID 전달
            user_session=request.headers.get("X-Session-Id"),
            features=info.features,
            target_customer=info.target_customer,
            tone=info.tone
        )
        
    except Exception as e:
        print(f"❌ Product 생성 실패: {e}")
        # Product 생성 실패 시 에러 응답
        return handle_kafka_production(producer, {
            "html_list": [],
            "error": f"Product 생성 실패: {str(e)}"
        })
    
    if result["success"]:
        print(f"✅ 작업 제출 완료: {result['task_id']}")
        
        # 즉시 성공 응답 반환 (실제 결과는 나중에 조회)
        kafka_response = handle_kafka_production(producer, {
            "html_list": [],  # Worker가 처리 중
            "task_id": result["task_id"],
            "message": "작업이 Worker 서비스로 전달되었습니다"
        })
        
        # task_id를 최상위 레벨에 추가
        kafka_response["task_id"] = result["task_id"]
        return kafka_response
    else:
        print(f"❌ 작업 제출 실패: {result.get('error')}")
        return handle_kafka_production(producer, {
            "html_list": [],
            "error": result.get('error', 'Worker 서비스 연결 실패')
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
    print(f"🖼️ 이미지 생성 요청: {user_id}")
    
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
        
        print(f"💾 파일 저장 완료: {filepath}")
        print(f"🔗 접근 URL: {saved_url}")
        
        return {"filepath": filepath, "saved_url": saved_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류 발생: {str(e)}")

@router.get("/generation/status/{task_id}", tags=["Products"])
async def get_generation_status(
    task_id: str,
    user_id: str = Depends(get_user_id)
):
    """HTML 생성 작업의 상태를 조회하는 엔드포인트"""
    from src.services.task_manager import task_manager
    
    print(f"📊 작업 상태 조회: {task_id}")
    
    result = task_manager.get_task_status(task_id)
    
    if result["success"]:
        return result
    else:
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Task not found")
        )

@router.get("/generation/result/{task_id}", tags=["Products"])
async def get_generation_result(
    task_id: str,
    user_id: str = Depends(get_user_id)
):
    """HTML 생성 작업의 결과를 조회하는 엔드포인트"""
    from src.services.task_manager import task_manager
    
    print(f"📋 작업 결과 조회: {task_id}")
    
    result = task_manager.get_task_result(task_id)
    
    if result["success"]:
        return result
    else:
        # 작업이 아직 완료되지 않은 경우
        if result.get("status") and result["status"] != "completed":
            return {
                "success": False,
                "task_id": task_id,
                "status": result["status"],
                "message": result.get("message", f"Task is {result['status']}")
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Result not found")
            )

@router.get("/product-details/{product_details_id}", tags=["Products"])
async def get_product_details(
    product_details_id: int,
    user_id: str = Depends(get_optional_user_id)
):
    """ProductDetails ID로 상품 상세 정보 조회"""
    print(f"📋 상품 상세 조회: {product_details_id}")
    
    with simple_db.get_session() as db:
        try:
            # ProductDetails 조회
            product_details = db.query(ProductDetails).filter(
                ProductDetails.id == product_details_id
            ).first()
            
            if not product_details:
                raise HTTPException(
                    status_code=404, 
                    detail=f"ProductDetails {product_details_id}를 찾을 수 없습니다"
                )
            
            # 관련 이미지들도 함께 조회
            product_images = db.query(ProductImage).filter(
                ProductImage.product_details_id == product_details_id
            ).all()
            
            result = product_details.to_dict()
            result["product_images"] = [img.to_dict() for img in product_images]
            
            print(f"✅ 상품 상세 조회 완료: {product_details_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ 상품 상세 조회 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"조회 중 오류 발생: {str(e)}"
            )

@router.get("/product-details", tags=["Products"])
async def list_product_details(
    user_id: str = Depends(get_user_id),
    status: str = None,
    limit: int = 20,
    offset: int = 0
):
    """사용자의 ProductDetails 목록 조회"""
    print(f"📋 상품 목록 조회: user_id={user_id}, status={status}")
    
    with simple_db.get_session() as db:
        try:
            # 기본 쿼리
            query = db.query(ProductDetails).filter(ProductDetails.user_id == user_id)
            
            # 상태 필터링
            if status:
                query = query.filter(ProductDetails.status == status)
            
            # 정렬 및 페이징
            query = query.order_by(ProductDetails.created_at.desc())
            total = query.count()
            
            product_details_list = query.offset(offset).limit(limit).all()
            
            result = {
                "total": total,
                "items": [pd.to_dict() for pd in product_details_list],
                "limit": limit,
                "offset": offset
            }
            
            print(f"✅ 상품 목록 조회 완료: {total}개")
            return result
            
        except Exception as e:
            print(f"❌ 상품 목록 조회 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"조회 중 오류 발생: {str(e)}"
            )

@router.put("/product-details/{product_details_id}", 
           response_model=ProductDetailsResponse,
           tags=["Products"])
async def update_product_details(
    product_details_id: int,
    update_data: ProductDetailsUpdate,
    user_id: str = Depends(get_user_id)
):
    """ProductDetails 업데이트 엔드포인트"""
    print(f"📝 상품 상세 업데이트 요청: {product_details_id} by {user_id}")
    
    with simple_db.get_session() as db:
        try:
            # ProductDetails 조회 및 권한 확인
            product_details = db.query(ProductDetails).filter(
                ProductDetails.id == product_details_id,
                ProductDetails.user_id == user_id  # 본인만 수정 가능
            ).first()
            
            if not product_details:
                raise HTTPException(
                    status_code=404,
                    detail=f"ProductDetails {product_details_id}를 찾을 수 없거나 수정 권한이 없습니다"
                )
            
            # 업데이트할 필드들 처리
            updated_fields = []
            
            if update_data.product_id is not None:
                product_details.product_id = update_data.product_id
                updated_fields.append("product_id")
            
            if update_data.original_product_info is not None:
                product_details.original_product_info = update_data.original_product_info.strip()
                updated_fields.append("original_product_info")
            
            if update_data.generated_html is not None:
                product_details.generated_html = update_data.generated_html
                updated_fields.append("generated_html")
            
            if update_data.status is not None:
                if update_data.status not in ['draft', 'published', 'archived']:
                    raise HTTPException(
                        status_code=400,
                        detail="status는 'draft', 'published', 'archived' 중 하나여야 합니다"
                    )
                product_details.status = update_data.status
                updated_fields.append("status")
            
            if not updated_fields:
                return ProductDetailsResponse(
                    success=False,
                    message="업데이트할 필드가 없습니다"
                )
            
            # updated_at 자동 갱신 (SQLAlchemy onupdate가 처리)
            db.commit()
            db.refresh(product_details)
            
            print(f"✅ 상품 상세 업데이트 완료: {product_details_id}, 필드: {updated_fields}")
            
            return ProductDetailsResponse(
                success=True,
                message=f"상품 상세 정보가 업데이트되었습니다 (필드: {', '.join(updated_fields)})",
                data=product_details.to_dict()
            )
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ 상품 상세 업데이트 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"업데이트 중 오류 발생: {str(e)}"
            )

@router.delete("/product-details/{product_details_id}", 
              response_model=ProductDetailsResponse,
              tags=["Products"])
async def delete_product_details(
    product_details_id: int,
    user_id: str = Depends(get_user_id)
):
    """ProductDetails 삭제 엔드포인트 (연관된 이미지도 함께 삭제)"""
    print(f"🗑️ 상품 상세 삭제 요청: {product_details_id} by {user_id}")
    
    with simple_db.get_session() as db:
        try:
            # ProductDetails 조회 및 권한 확인
            product_details = db.query(ProductDetails).filter(
                ProductDetails.id == product_details_id,
                ProductDetails.user_id == user_id  # 본인만 삭제 가능
            ).first()
            
            if not product_details:
                raise HTTPException(
                    status_code=404,
                    detail=f"ProductDetails {product_details_id}를 찾을 수 없거나 삭제 권한이 없습니다"
                )
            
            # 연관된 이미지 수 확인
            image_count = db.query(ProductImage).filter(
                ProductImage.product_details_id == product_details_id
            ).count()
            
            # 삭제 실행 (CASCADE로 인해 연관된 ProductImage도 자동 삭제됨)
            db.delete(product_details)
            db.commit()
            
            print(f"✅ 상품 상세 삭제 완료: {product_details_id} (이미지 {image_count}개 포함)")
            
            return ProductDetailsResponse(
                success=True,
                message=f"상품 상세 정보가 삭제되었습니다 (연관 이미지 {image_count}개 포함)",
                data={
                    "deleted_product_details_id": product_details_id,
                    "deleted_image_count": image_count
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ 상품 상세 삭제 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"삭제 중 오류 발생: {str(e)}"
            )

@router.post("/test/notification", tags=["Test"])
async def test_notification_flow(
    user_id: str = Depends(get_user_id)
):
    """알림 플로우 테스트를 위한 간단한 작업 등록 엔드포인트"""
    from src.services.task_manager import task_manager
    
    print(f"🧪 알림 플로우 테스트 시작 - 사용자: {user_id}")
    
    try:
        # 간단한 테스트 작업 등록
        result = task_manager.submit_task(
            product_data="테스트 상품 - 알림 플로우 검증용",
            product_image_url="https://placehold.co/400x300/png?text=Test+Product",
            user_id=user_id,
            user_session="test-session"
        )
        
        if result["success"]:
            print(f"✅ 테스트 작업 등록 완료: {result['task_id']}")
            return {
                "success": True,
                "message": "테스트 작업이 등록되었습니다. Worker 서비스에서 처리 후 알림을 발송합니다.",
                "task_id": result["task_id"],
                "instructions": [
                    "1. Worker 서비스에서 이 작업을 처리합니다",
                    "2. 처리 완료 후 Event Hub로 알림 이벤트를 발송합니다",
                    "3. 알림 서비스에서 이벤트를 수신하여 알림을 처리합니다"
                ]
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"작업 등록 실패: {result.get('error')}"
            )
            
    except Exception as e:
        print(f"❌ 테스트 작업 등록 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"테스트 실행 중 오류: {str(e)}"
        )
    