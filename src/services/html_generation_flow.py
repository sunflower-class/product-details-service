"""
HTML 생성 전체 플로우 서비스
Product 생성 → 이미지 생성 → S3 업로드 → HTML 생성 → DB 저장
"""
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from src.services.product_client import product_client, parse_product_data
from src.services.image_manager import image_manager
from src.services.create_html_hybrid import generate_hybrid_html
from src.models.models_simple import ProductDetails, ProductImage, simple_db

class HtmlGenerationFlow:
    """HTML 생성 전체 플로우 관리"""
    
    def __init__(self):
        self.max_images = 3  # 생성할 최대 이미지 수
    
    async def generate_complete_html(
        self,
        product_data: str,
        product_image_url: str,
        user_id: str,
        user_session: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        전체 HTML 생성 플로우 실행
        
        Args:
            product_data: 상품 정보 텍스트
            product_image_url: 원본 상품 이미지 URL
            user_id: 사용자 ID
            user_session: 세션 ID (선택)
            
        Returns:
            생성 결과 딕셔너리
        """
        
        product_details_id = None
        
        try:
            print(f"🚀 HTML 생성 플로우 시작 - 사용자: {user_id}")
            
            # 1. Product 서비스에 상품 생성
            print("1️⃣ Product 서비스에 상품 생성 중...")
            product_request = parse_product_data(product_data, user_id)
            product_response = await product_client.create_product(product_request)
            
            if not product_response:
                raise Exception("Product 서비스 호출 실패")
            
            product_id = product_response.productId
            print(f"✅ Product 생성 완료 - ID: {product_id}")
            
            # 2. ProductDetails 레코드 생성 (먼저 생성해야 이미지에서 참조 가능)
            print("2️⃣ ProductDetails 레코드 생성 중...")
            with simple_db.get_session() as db:
                product_details = ProductDetails(
                    product_id=product_id,
                    user_id=user_id,
                    user_session=user_session,
                    original_product_info=product_data,
                    generated_html={"status": "generating"},  # 임시 상태
                    used_templates=[],
                    used_categories=[],
                    status='draft'
                )
                
                db.add(product_details)
                db.flush()  # ID 생성
                product_details_id = product_details.id
                
                print(f"✅ ProductDetails 생성 완료 - ID: {product_details_id}")
            
            # 3. 원본 이미지 저장 (ORIGINAL)
            print("3️⃣ 원본 이미지 저장 중...")
            original_image_data = await self._store_original_image(
                product_details_id, product_image_url, user_id, product_id
            )
            
            if not original_image_data:
                raise Exception("원본 이미지 저장 실패")
            
            # 4. 추가 이미지 생성 (GENERATED)
            print("4️⃣ 추가 이미지 생성 중...")
            generated_images = await self._generate_additional_images(
                product_details_id, product_data, user_id, product_id
            )
            
            # 최소 1개 이미지는 있어야 함 (원본)
            if not generated_images and not original_image_data:
                raise Exception("모든 이미지 생성/저장 실패")
            
            # 5. 모든 이미지 수집
            all_images = [original_image_data] + generated_images
            image_urls = [img['url'] for img in all_images if img and img.get('url')]
            
            print(f"📸 사용할 이미지 {len(image_urls)}개 준비 완료")
            
            if not image_urls:
                raise Exception("사용 가능한 이미지 URL 없음")
            
            # 6. HTML 생성 (이미지 URL들 포함)
            print("6️⃣ HTML 생성 중...")
            html_list = self._generate_html_with_images(product_data, image_urls)
            
            if not html_list:
                raise Exception("HTML 생성 실패")
            
            # 7. ProductDetails 업데이트 (최종 HTML 저장)
            print("7️⃣ 최종 결과 저장 중...")
            with simple_db.get_session() as db:
                product_details = db.query(ProductDetails).filter(
                    ProductDetails.id == product_details_id
                ).first()
                
                if not product_details:
                    raise Exception("ProductDetails 레코드를 찾을 수 없음")
                
                product_details.generated_html = {
                    "html_blocks": html_list,
                    "image_count": len(image_urls),
                    "generation_completed": True
                }
                product_details.status = 'completed'
            
            print("✅ HTML 생성 플로우 완료!")
            
            return {
                "success": True,
                "product_details_id": product_details_id,
                "product_id": product_id,
                "html_list": html_list,
                "image_count": len(image_urls),
                "images": all_images
            }
            
        except Exception as e:
            print(f"❌ HTML 생성 플로우 실패: {e}")
            
            # 실패 시 ProductDetails를 failed 상태로 마크
            if product_details_id:
                try:
                    with simple_db.get_session() as db:
                        product_details = db.query(ProductDetails).filter(
                            ProductDetails.id == product_details_id
                        ).first()
                        
                        if product_details:
                            product_details.status = 'failed'
                            product_details.generated_html = {
                                "error": str(e),
                                "failed_at": datetime.now().isoformat()
                            }
                            print(f"📝 ProductDetails {product_details_id} 실패 상태로 마크")
                except Exception as cleanup_error:
                    print(f"⚠️ 실패 상태 저장 중 오류: {cleanup_error}")
            
            return {
                "success": False,
                "error": str(e),
                "product_details_id": product_details_id,
                "fallback_html": generate_hybrid_html(product_data, product_image_url)
            }
    
    async def _store_original_image(
        self,
        product_details_id: int,
        image_url: str,
        user_id: str,
        product_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """원본 이미지를 ORIGINAL로 저장"""
        
        try:
            with simple_db.get_session() as db:
                original_image = ProductImage(
                    product_details_id=product_details_id,
                    product_id=product_id,
                    user_id=user_id,
                    temp_url=image_url,
                    image_source='ORIGINAL',
                    image_type='product',
                    is_uploaded_to_s3=False
                )
                
                db.add(original_image)
                db.commit()
                
                return {
                    'id': original_image.id,
                    'url': image_url,
                    'image_source': 'ORIGINAL',
                    'image_type': 'product'
                }
                
        except Exception as e:
            print(f"❌ 원본 이미지 저장 실패: {e}")
            return None
    
    async def _generate_additional_images(
        self,
        product_details_id: int,
        product_data: str,
        user_id: str,
        product_id: Optional[int]
    ) -> List[Dict[str, Any]]:
        """추가 이미지들을 생성"""
        
        generated_images = []
        
        # 상품 데이터에서 이미지 프롬프트 추출
        prompts = self._extract_image_prompts(product_data)
        
        for i, prompt in enumerate(prompts[:self.max_images]):
            print(f"🎨 이미지 {i+1} 생성 중: {prompt[:50]}...")
            
            image_data = image_manager.generate_and_store_image(
                product_details_id=product_details_id,
                prompt=prompt,
                user_id=user_id,
                image_type='product',
                product_id=product_id
            )
            
            if image_data and not image_data.get('error'):
                generated_images.append(image_data)
                print(f"✅ 이미지 {i+1} 생성 완료")
            else:
                # 이미지 생성 실패 시 에러 발생 (전체 플로우 중단)
                error_msg = image_data.get('error', 'Unknown error') if image_data else 'No response'
                raise Exception(f"이미지 {i+1} 생성 실패: {error_msg}")
        
        return generated_images
    
    def _extract_image_prompts(self, product_data: str) -> List[str]:
        """상품 데이터에서 이미지 프롬프트 추출"""
        
        # 기본 프롬프트들
        base_prompts = [
            f"Product showcase: {product_data[:100]}",
            f"High quality product image: {product_data[:100]}",
            f"Commercial product photography: {product_data[:100]}"
        ]
        
        # 상품 데이터에서 키워드 추출하여 더 구체적인 프롬프트 생성
        keywords = []
        
        # 간단한 키워드 추출
        for line in product_data.lower().split('\n'):
            if any(word in line for word in ['색상', 'color', '재질', 'material', '크기', 'size']):
                keywords.append(line.strip())
        
        # 키워드 기반 프롬프트 추가
        if keywords:
            for keyword in keywords[:2]:  # 최대 2개
                base_prompts.append(f"Product with {keyword}: professional photography")
        
        return base_prompts[:self.max_images]
    
    def _generate_html_with_images(self, product_data: str, image_urls: List[str]) -> List[str]:
        """이미지 URL들을 포함하여 HTML 생성"""
        
        try:
            # 기존 하이브리드 생성 방식 사용, 하지만 이미지는 우리가 생성한 것들 사용
            primary_image = image_urls[0] if image_urls else "https://via.placeholder.com/400x300"
            
            # 하이브리드 HTML 생성
            html_list = generate_hybrid_html(product_data, primary_image)
            
            # 추가 이미지들을 HTML에 삽입
            if len(image_urls) > 1:
                additional_images_html = self._create_image_gallery_html(image_urls[1:])
                html_list.append(additional_images_html)
            
            return html_list
            
        except Exception as e:
            print(f"❌ HTML 생성 실패: {e}")
            # 폴백: 기본 HTML
            return [f"<div><h3>상품 정보</h3><p>{product_data}</p></div>"]
    
    def _create_image_gallery_html(self, image_urls: List[str]) -> str:
        """추가 이미지들로 갤러리 HTML 생성"""
        
        gallery_items = []
        for url in image_urls:
            gallery_items.append(f'''
                <div style="flex: 1; margin: 10px;">
                    <img src="{url}" alt="Product Image" style="width: 100%; height: 200px; object-fit: cover; border-radius: 8px;" />
                </div>
            ''')
        
        return f'''
        <div style="margin: 20px 0;">
            <h4 style="margin-bottom: 15px; color: #333;">추가 상품 이미지</h4>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                {"".join(gallery_items)}
            </div>
        </div>
        '''

# 글로벌 인스턴스
html_flow = HtmlGenerationFlow()