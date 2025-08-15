"""
Product 서비스 HTTP 클라이언트
상품 데이터를 Product 서비스에 저장하고 관리
"""
import os
import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

class ProductCreateRequest(BaseModel):
    """Product 서비스로 보낼 상품 생성 요청"""
    name: str  # 상품명
    description: str  # 상품 설명
    category: Optional[str] = None  # 카테고리
    price: Optional[float] = None  # 가격
    brand: Optional[str] = None  # 브랜드
    status: str = 'ACTIVE'  # 상태 (ACTIVE, INACTIVE, DRAFT)
    user_id: str  # 사용자 ID
    source: str = 'DETAIL_SERVICE'  # 출처
    metadata: Optional[str] = None  # 추가 메타데이터 (JSON 문자열)

class ProductResponse(BaseModel):
    """Product 서비스 응답"""
    productId: int  # camelCase로 변경
    userId: str
    name: str
    description: str
    category: str
    price: float
    brand: Optional[str]
    source: str
    status: str
    metadata: str
    createdAt: str  # camelCase로 변경
    updatedAt: str  # camelCase로 변경

class ProductClient:
    """Product 서비스 HTTP 클라이언트"""
    
    def __init__(self):
        self.base_url = os.getenv('PRODUCT_SERVICE_URL', 'http://product-service')
        self.timeout = 30.0
    
    async def create_product(self, product_data: ProductCreateRequest) -> Optional[ProductResponse]:
        """
        상품을 Product 서비스에 생성합니다.
        
        Args:
            product_data: 상품 생성 데이터
            
        Returns:
            생성된 상품 정보 또는 None (실패 시)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/products",
                    json=product_data.dict(),
                    headers={
                        'Content-Type': 'application/json',
                        'X-User-Id': product_data.user_id  # X-User-Id 헤더 추가
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return ProductResponse(**data)
                else:
                    print(f"❌ Product 생성 실패: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            print("❌ Product 서비스 타임아웃")
            return None
        except Exception as e:
            print(f"❌ Product 서비스 요청 실패: {e}")
            return None
    
    async def get_product(self, product_id: int) -> Optional[ProductResponse]:
        """
        Product ID로 상품 정보를 조회합니다.
        
        Args:
            product_id: 상품 ID
            
        Returns:
            상품 정보 또는 None (실패 시)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/products/{product_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    return ProductResponse(**data)
                else:
                    print(f"❌ Product 조회 실패: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"❌ Product 서비스 요청 실패: {e}")
            return None
    
    async def update_product(self, product_id: int, update_data: Dict[str, Any]) -> Optional[ProductResponse]:
        """
        상품 정보를 업데이트합니다.
        
        Args:
            product_id: 상품 ID
            update_data: 업데이트할 데이터
            
        Returns:
            업데이트된 상품 정보 또는 None (실패 시)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    f"{self.base_url}/api/products/{product_id}",
                    json=update_data,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return ProductResponse(**data)
                else:
                    print(f"❌ Product 업데이트 실패: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"❌ Product 서비스 요청 실패: {e}")
            return None

def parse_product_data(product_data_str: str, user_id: str) -> ProductCreateRequest:
    """
    ProductInfo의 product_data 문자열을 파싱하여 ProductCreateRequest로 변환
    
    Args:
        product_data_str: 사용자가 입력한 상품 정보 문자열
        user_id: 사용자 ID
        
    Returns:
        파싱된 상품 생성 요청
    """
    # 간단한 텍스트 파싱 로직
    # 실제로는 더 정교한 파싱이나 LLM을 사용할 수 있음
    
    lines = product_data_str.strip().split('\n')
    
    # 기본값
    name = "상품명 없음"
    description = product_data_str.strip()
    category = None
    price = None
    brand = None
    
    # 간단한 키워드 기반 파싱
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 첫 번째 줄을 상품명으로 사용 (길이 제한)
        if name == "상품명 없음" and len(line) < 100:
            name = line
        
        # 가격 정보 추출
        if any(keyword in line.lower() for keyword in ['price', '가격', '원', '$', '₩']):
            import re
            price_match = re.search(r'[\d,]+', line.replace(',', ''))
            if price_match:
                try:
                    price = float(price_match.group().replace(',', ''))
                except:
                    pass
        
        # 브랜드 정보 추출
        if any(keyword in line.lower() for keyword in ['brand', '브랜드', 'maker', '제조사']):
            brand_part = line.split(':')[-1].strip() if ':' in line else line
            if len(brand_part) < 50:
                brand = brand_part
        
        # 카테고리 정보 추출
        if any(keyword in line.lower() for keyword in ['category', '카테고리', 'type', '종류']):
            category_part = line.split(':')[-1].strip() if ':' in line else line
            if len(category_part) < 50:
                category = category_part
    
    import json
    
    metadata_dict = {
        'original_input': product_data_str,
        'parsed_at': datetime.now().isoformat()
    }
    
    return ProductCreateRequest(
        name=name,
        description=description,
        category=category if category else "기타",  # 기본값: "기타"
        price=price if price else 0,  # 기본값: 0
        brand=brand,
        user_id=user_id,  # Product 서비스에서 UUID 변환 처리
        metadata=json.dumps(metadata_dict)  # JSON 문자열로 변환
    )

# 글로벌 인스턴스
product_client = ProductClient()