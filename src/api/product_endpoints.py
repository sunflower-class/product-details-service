"""
Product CRUD API 엔드포인트
상품 관리를 위한 REST API
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Header, Query, Path, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from src.services.product_service import ProductService


# Pydantic 스키마들
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=200, description="상품명")
    description: Optional[str] = Field(None, description="상품 설명")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")
    brand: Optional[str] = Field(None, max_length=100, description="브랜드")
    price: Optional[float] = Field(None, ge=0, description="가격")
    currency: Optional[str] = Field("KRW", max_length=3, description="통화")
    original_product_data: str = Field(..., description="원본 상품 데이터")
    main_image_url: Optional[str] = Field(None, max_length=500, description="메인 이미지 URL")
    features: Optional[List[str]] = Field(None, description="상품 특징")
    target_customer: Optional[str] = Field(None, max_length=200, description="타겟 고객층")
    tone: Optional[str] = Field(None, max_length=50, description="톤앤매너")
    status: Optional[str] = Field("active", description="상품 상태")
    is_published: Optional[bool] = Field(False, description="퍼블리시 여부")

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200, description="상품명")
    description: Optional[str] = Field(None, description="상품 설명")
    category: Optional[str] = Field(None, max_length=100, description="카테고리")
    brand: Optional[str] = Field(None, max_length=100, description="브랜드")
    price: Optional[float] = Field(None, ge=0, description="가격")
    currency: Optional[str] = Field(None, max_length=3, description="통화")
    original_product_data: Optional[str] = Field(None, description="원본 상품 데이터")
    main_image_url: Optional[str] = Field(None, max_length=500, description="메인 이미지 URL")
    features: Optional[List[str]] = Field(None, description="상품 특징")
    target_customer: Optional[str] = Field(None, max_length=200, description="타겟 고객층")
    tone: Optional[str] = Field(None, max_length=50, description="톤앤매너")
    status: Optional[str] = Field(None, description="상품 상태")
    is_published: Optional[bool] = Field(None, description="퍼블리시 여부")

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    brand: Optional[str]
    price: Optional[float]
    currency: str
    original_product_data: str
    main_image_url: Optional[str]
    features: Optional[List[str]]
    target_customer: Optional[str]
    tone: Optional[str]
    status: str
    is_published: bool
    view_count: int
    user_id: str
    user_session: Optional[str]
    created_at: str
    updated_at: str
    published_at: Optional[str]

class ProductWithDetailsResponse(ProductResponse):
    product_details: List[Dict[str, Any]]
    product_details_count: int


# FastAPI Router
router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    x_user_id: str = Header(..., description="사용자 ID"),
    x_user_session: Optional[str] = Header(None, description="사용자 세션")
):
    """새 상품 생성"""
    try:
        product = ProductService.create_product(
            product_data=product_data.dict(),
            user_id=x_user_id,
            user_session=x_user_session
        )
        return ProductResponse(**product.to_dict())
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 생성 실패: {str(e)}")


@router.get("/", response_model=List[ProductResponse])
async def get_products(
    x_user_id: Optional[str] = Header(None, description="사용자 ID (없으면 모든 상품 조회)"),
    status: Optional[str] = Query(None, description="상품 상태 필터"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    search: Optional[str] = Query(None, description="검색어 (상품명, 설명, 브랜드)"),
    is_published: Optional[bool] = Query(None, description="퍼블리시 상태 필터"),
    skip: int = Query(0, ge=0, description="건너뛸 항목 수"),
    limit: int = Query(20, ge=1, le=100, description="조회할 항목 수")
):
    """상품 목록 조회"""
    try:
        products = ProductService.get_products(
            user_id=x_user_id,
            status=status,
            category=category,
            search=search,
            is_published=is_published,
            skip=skip,
            limit=limit
        )
        return [ProductResponse(**product.to_dict()) for product in products]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 목록 조회 실패: {str(e)}")


@router.get("/stats")
async def get_product_stats(
    x_user_id: Optional[str] = Header(None, description="사용자 ID (없으면 전체 통계)")
):
    """상품 통계 조회"""
    try:
        stats = ProductService.get_product_stats(user_id=x_user_id)
        return {
            "success": True,
            "data": stats
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int = Path(..., description="상품 ID"),
    x_user_id: Optional[str] = Header(None, description="사용자 ID (없으면 관리자 모드)")
):
    """특정 상품 조회"""
    try:
        product = ProductService.get_product_by_id(
            product_id=product_id,
            user_id=x_user_id
        )
        
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
        
        # 조회수 증가
        ProductService.increase_view_count(product_id)
        
        return ProductResponse(**product.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 조회 실패: {str(e)}")


@router.get("/{product_id}/with-details", response_model=ProductWithDetailsResponse)
async def get_product_with_details(
    product_id: int = Path(..., description="상품 ID"),
    x_user_id: Optional[str] = Header(None, description="사용자 ID (없으면 관리자 모드)")
):
    """상품과 연관된 상세페이지들을 함께 조회"""
    try:
        product_data = ProductService.get_product_with_details(
            product_id=product_id,
            user_id=x_user_id
        )
        
        if not product_data:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
        
        # 조회수 증가
        ProductService.increase_view_count(product_id)
        
        return ProductWithDetailsResponse(**product_data)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 조회 실패: {str(e)}")


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int = Path(..., description="상품 ID"),
    product_data: ProductUpdate = ...,
    x_user_id: str = Header(..., description="사용자 ID")
):
    """상품 정보 수정"""
    try:
        # None이 아닌 값들만 업데이트
        update_data = {k: v for k, v in product_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="업데이트할 데이터가 없습니다")
        
        product = ProductService.update_product(
            product_id=product_id,
            product_data=update_data,
            user_id=x_user_id
        )
        
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없거나 권한이 없습니다")
        
        return ProductResponse(**product.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 수정 실패: {str(e)}")


@router.delete("/{product_id}")
async def delete_product(
    product_id: int = Path(..., description="상품 ID"),
    x_user_id: str = Header(..., description="사용자 ID")
):
    """상품 삭제 (연관된 상세페이지들도 함께 삭제됨)"""
    try:
        success = ProductService.delete_product(
            product_id=product_id,
            user_id=x_user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없거나 권한이 없습니다")
        
        return {
            "success": True,
            "message": "상품이 성공적으로 삭제되었습니다"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"상품 삭제 실패: {str(e)}")


@router.patch("/{product_id}/publish")
async def toggle_product_publish(
    product_id: int = Path(..., description="상품 ID"),
    x_user_id: str = Header(..., description="사용자 ID"),
    is_published: bool = Query(..., description="퍼블리시 상태")
):
    """상품 퍼블리시 상태 변경"""
    try:
        product = ProductService.update_product(
            product_id=product_id,
            product_data={"is_published": is_published},
            user_id=x_user_id
        )
        
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없거나 권한이 없습니다")
        
        return {
            "success": True,
            "message": f"상품이 {'퍼블리시' if is_published else '비공개'}되었습니다",
            "is_published": product.is_published,
            "published_at": product.published_at.isoformat() if product.published_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"퍼블리시 상태 변경 실패: {str(e)}")