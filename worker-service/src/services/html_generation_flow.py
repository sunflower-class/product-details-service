"""
HTML 생성 전체 플로우 서비스
Product 생성 → 이미지 생성 → S3 업로드 → HTML 생성 → DB 저장
"""
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

# ProductService 제거 - worker는 ProductDetails만 처리
from src.services.image_manager import image_manager
from src.services.create_html_hybrid import generate_hybrid_html
from src.models.models_simple import ProductDetails, ProductImage, simple_db

class HtmlGenerationFlow:
    """HTML 생성 전체 플로우 관리"""
    
    def __init__(self):
        import os
        # 환경 변수로 이미지 생성 수 제어 (기본값 2로 변경 - 테스트용)
        self.max_images = int(os.environ.get("MAX_GENERATED_IMAGES", "2"))
    
    async def generate_complete_html(
        self,
        product_data: str,
        product_image_url: str,
        user_id: str,
        user_session: Optional[str] = None,
        task_data: Optional[Dict[str, Any]] = None,
        features: Optional[List[str]] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        전체 HTML 생성 플로우 실행
        
        Args:
            product_data: 상품 정보 텍스트
            product_image_url: 원본 상품 이미지 URL
            user_id: 사용자 ID
            user_session: 세션 ID (선택)
            task_data: 작업 관련 데이터
            features: 상품 주요 특징 목록
            target_customer: 타겟 고객층
            tone: 톤앤매너 (예: professional, casual, friendly)
            
        Returns:
            생성 결과 딕셔너리
        """
        
        product_details_id = None
        
        # task_data 기본값 설정
        if task_data is None:
            task_data = {"task_id": "unknown"}
        
        try:
            print(f"🚀 HTML 생성 플로우 시작 - 사용자: {user_id}")
            
            # 1. task_data에서 product_id 추출
            product_id = task_data.get('product_id') if task_data else None
            if not product_id:
                raise Exception("Product ID가 task_data에 없습니다")
            
            print(f"📋 Product ID 확인: {product_id}")
            
            # 2. ProductDetails 레코드 생성 (메인 서비스에서 생성된 Product ID 사용)
            print("1️⃣ ProductDetails 레코드 생성 중...")
            with simple_db.get_session() as db:
                # 추가 정보를 metadata에 저장
                metadata = {
                    "generation_settings": {
                        "features": features or [],
                        "target_customer": target_customer,
                        "tone": tone or "professional"
                    },
                    "status": "generating"
                }
                
                product_details = ProductDetails(
                    product_id=product_id,  # 메인 서비스에서 생성된 Product ID 사용
                    user_id=user_id,
                    user_session=user_session,
                    original_product_info=product_data,
                    generated_html=metadata,  # 생성 설정 포함
                    used_templates=[],
                    used_categories=[],
                    status='draft'
                )
                
                db.add(product_details)
                db.flush()  # ID 생성
                product_details_id = product_details.id
                
                print(f"✅ ProductDetails 생성 완료 - ID: {product_details_id}")
            
            # 3. 원본 이미지 저장 (ORIGINAL)
            print("2️⃣ 원본 이미지 저장 중...")
            original_image_data = await self._store_original_image(
                product_details_id, product_image_url, user_id, product_id
            )
            
            if not original_image_data:
                raise Exception("원본 이미지 저장 실패")
            
            # 4. 추가 이미지 생성 (GENERATED)
            print("4️⃣ 추가 이미지 생성 중...")
            generated_images = await self._generate_additional_images(
                product_details_id, product_data, user_id, product_id,
                features=features, target_customer=target_customer, tone=tone
            )
            
            # 원본 이미지가 있으면 계속 진행 (추가 이미지 실패는 허용)
            if not original_image_data:
                raise Exception("원본 이미지 저장 실패")
            elif not generated_images:
                print("⚠️ 추가 이미지 생성 실패, 원본 이미지만 사용")
            
            # 5. 모든 이미지 수집
            all_images = [original_image_data] + generated_images
            image_urls = [img['url'] for img in all_images if img and img.get('url')]
            
            print(f"📸 사용할 이미지 {len(image_urls)}개 준비 완료")
            
            if not image_urls:
                raise Exception("사용 가능한 이미지 URL 없음")
            
            # 6. HTML 생성 (이미지 URL들 포함)
            print("6️⃣ HTML 생성 중...")
            html_list = self._generate_html_with_images(
                product_data, image_urls, features=features, 
                target_customer=target_customer, tone=tone
            )
            
            if not html_list:
                raise Exception("HTML 생성 실패")
            
            # 7. ProductDetails 업데이트 (최종 HTML 저장 및 썸네일 설정)
            print("7️⃣ 최종 결과 저장 중...")
            with simple_db.get_session() as db:
                product_details = db.query(ProductDetails).filter(
                    ProductDetails.id == product_details_id
                ).first()
                
                if not product_details:
                    raise Exception("ProductDetails 레코드를 찾을 수 없음")
                
                # 첫 번째 이미지를 썸네일로 설정
                thumbnail_url = None
                if image_urls:
                    # S3에 업로드된 첫 번째 이미지의 URL을 썸네일로 사용
                    first_image = db.query(ProductImage).filter(
                        ProductImage.product_details_id == product_details_id,
                        ProductImage.s3_url.isnot(None),
                        ProductImage.is_uploaded_to_s3 == True
                    ).order_by(ProductImage.created_at.asc()).first()
                    
                    if first_image:
                        thumbnail_url = first_image.s3_url
                        print(f"📸 썸네일 설정: {thumbnail_url}")
                
                product_details.generated_html = {
                    "html_blocks": html_list,
                    "image_count": len(image_urls),
                    "generation_completed": True
                }
                product_details.status = 'completed'
                product_details.thumbnail = thumbnail_url
            
            print("✅ HTML 생성 플로우 완료!")
            
            # 8. 성공 알림 발송 (Kafka 이벤트 허브로)
            try:
                from src.services.notification_service import notification_service
                
                notification_sent = notification_service.send_success_notification(
                    user_id=user_id,
                    product_details_id=str(product_details_id),
                    task_id=task_data.get("task_id", "unknown"),
                    user_session=user_session
                )
                
                if notification_sent:
                    print(f"📤 성공 알림 발송 완료: {user_id}")
                else:
                    print(f"⚠️ 성공 알림 발송 실패: {user_id}")
                    
            except Exception as notification_error:
                print(f"⚠️ 알림 발송 중 오류 (작업은 성공): {notification_error}")
            
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
            
            # 실패 알림 발송 (Kafka 이벤트 허브로)
            try:
                from src.services.notification_service import notification_service
                
                notification_sent = notification_service.send_error_notification(
                    user_id=user_id,
                    task_id=task_data.get("task_id", "unknown"),
                    error_message=str(e),
                    user_session=user_session
                )
                
                if notification_sent:
                    print(f"📤 실패 알림 발송 완료: {user_id}")
                else:
                    print(f"⚠️ 실패 알림 발송 실패: {user_id}")
                    
            except Exception as notification_error:
                print(f"⚠️ 실패 알림 발송 중 오류: {notification_error}")
            
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
            # 이미지 URL 접귀 가능성 간단 확인
            import requests
            print(f"🔍 원본 이미지 URL 확인 중: {image_url}")
            
            try:
                # 빠른 HEAD 요청으로 URL 유효성 확인
                response = requests.head(image_url, timeout=10)
                if response.status_code >= 400:
                    print(f"⚠️ 원본 이미지 URL 접귀 불가: HTTP {response.status_code}")
                    # URL이 잘못되어도 기본 플레이스홀더로 대체
                    image_url = "https://placehold.co/400x300/png?text=Product+Image"
            except Exception as url_check_error:
                print(f"⚠️ 원본 이미지 URL 확인 실패 ({url_check_error}), 플레이스홀더 사용")
                image_url = "https://placehold.co/400x300/png?text=Product+Image"
            
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
        product_id: Optional[int],
        features: Optional[List[str]] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """추가 이미지들을 생성"""
        
        generated_images = []
        
        # 상품 데이터에서 이미지 프롬프트 추출 (추가 정보 활용)
        prompts = self._extract_image_prompts(
            product_data, features=features, 
            target_customer=target_customer, tone=tone
        )
        
        for i, prompt in enumerate(prompts[:self.max_images]):
            print(f"🎨 이미지 {i+1}/{len(prompts[:self.max_images])} 생성 중: {prompt[:50]}...")
            
            # 타임아웃 60초로 이미지 생성 시도
            image_data = image_manager.generate_and_store_image(
                product_details_id=product_details_id,
                prompt=prompt,
                user_id=user_id,
                image_type='product',
                product_id=product_id,
                timeout=60  # 60초 타임아웃 설정
            )
            
            if image_data and not image_data.get('error'):
                generated_images.append(image_data)
                print(f"✅ 이미지 {i+1} 생성 완료")
            else:
                # 이미지 생성 실패 시 경고만 출력하고 계속 (전체 플로우 중단 방지)
                error_msg = image_data.get('error', 'Unknown error') if image_data else 'No response'
                print(f"⚠️ 이미지 {i+1} 생성 실패 (무시하고 계속): {error_msg}")
                
                # 타임아웃이나 API 오류 시에도 작업 계속 진행
                if 'timeout' in error_msg.lower():
                    print(f"⏰ 이미지 {i+1} 타임아웃으로 건너뛰고 다음 이미지로 진행")
                elif 'api error' in error_msg.lower():
                    print(f"🔌 이미지 {i+1} API 오류로 건너뛰고 다음 이미지로 진행")
        
        return generated_images
    
    def _extract_image_prompts(
        self, 
        product_data: str, 
        features: Optional[List[str]] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> List[str]:
        """상품 데이터에서 이미지 프롬프트 추출 (추가 정보 활용)"""
        
        # 톤에 따른 스타일 설정
        style_map = {
            "professional": "professional commercial photography, studio lighting, clean background",
            "casual": "lifestyle photography, natural lighting, everyday setting",
            "friendly": "warm and inviting photography, soft lighting, approachable style",
            "luxury": "premium luxury photography, dramatic lighting, elegant presentation"
        }
        
        photo_style = style_map.get(tone or "professional", style_map["professional"])
        
        # 기본 프롬프트들 (톤 반영)
        base_prompts = [
            f"High quality product showcase: {product_data[:80]}, {photo_style}",
            f"Product hero image: {product_data[:80]}, {photo_style}",
            f"Commercial product shot: {product_data[:80]}, {photo_style}"
        ]
        
        # 특징 기반 프롬프트 추가
        if features:
            for i, feature in enumerate(features[:2]):  # 최대 2개 특징 활용
                base_prompts.append(
                    f"Product highlighting {feature}: {product_data[:60]}, {photo_style}"
                )
        
        # 타겟 고객 기반 프롬프트 추가
        if target_customer:
            context_map = {
                "young": "modern, trendy, vibrant colors",
                "adult": "sophisticated, practical, clean design",
                "professional": "business setting, executive style, premium quality",
                "family": "family-friendly, home environment, everyday use",
                "seniors": "clear, simple, comfortable setting"
            }
            
            # 타겟 고객에서 키워드 추출
            customer_context = "lifestyle photography"
            for key, context in context_map.items():
                if key.lower() in target_customer.lower():
                    customer_context = context
                    break
            
            base_prompts.append(
                f"Product for {target_customer}: {product_data[:60]}, {customer_context}, {photo_style}"
            )
        
        # 상품 데이터에서 키워드 추출하여 더 구체적인 프롬프트 생성
        keywords = []
        for line in product_data.lower().split('\n'):
            if any(word in line for word in ['색상', 'color', '재질', 'material', '크기', 'size', '기능', 'feature']):
                keywords.append(line.strip()[:50])
        
        # 키워드 기반 프롬프트 추가
        if keywords:
            for keyword in keywords[:1]:  # 1개만 추가
                base_prompts.append(f"Product detail shot: {keyword}, {photo_style}")
        
        return base_prompts[:self.max_images]
    
    def _generate_html_with_images(
        self, 
        product_data: str, 
        image_urls: List[str],
        features: Optional[List[str]] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> List[str]:
        """이미지 URL들을 포함하여 HTML 생성 (추가 정보 활용)"""
        
        try:
            # 기존 하이브리드 생성 방식 사용, 하지만 이미지는 우리가 생성한 것들 사용
            primary_image = image_urls[0] if image_urls else "https://placehold.co/400x300/png?text=Product+Image"
            
            # 추가 정보를 반영한 상품 데이터 보강
            enhanced_product_data = self._enhance_product_data(
                product_data, features, target_customer, tone
            )
            
            # 하이브리드 HTML 생성 (보강된 데이터 사용)
            html_list = generate_hybrid_html(enhanced_product_data, primary_image)
            
            # 특징 하이라이트 HTML 추가
            if features:
                features_html = self._create_features_html(features, tone)
                html_list.append(features_html)
            
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
    
    def _enhance_product_data(
        self, 
        product_data: str, 
        features: Optional[List[str]] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> str:
        """추가 정보를 반영하여 상품 데이터 보강"""
        
        enhanced_parts = [product_data]
        
        # 타겟 고객 정보 추가
        if target_customer:
            enhanced_parts.append(f"\n\n타겟 고객: {target_customer}")
        
        # 주요 특징 추가
        if features:
            enhanced_parts.append(f"\n\n주요 특징:")
            for feature in features:
                enhanced_parts.append(f"• {feature}")
        
        # 톤앤매너 반영
        if tone:
            tone_context = {
                "professional": "전문적이고 신뢰할 수 있는",
                "casual": "편안하고 친근한",
                "friendly": "따뜻하고 다가가기 쉬운",
                "luxury": "프리미엄하고 고급스러운"
            }
            
            if tone in tone_context:
                enhanced_parts.append(f"\n\n브랜드 톤: {tone_context[tone]} 느낌으로 어필")
        
        return " ".join(enhanced_parts)
    
    def _create_features_html(self, features: List[str], tone: Optional[str] = None) -> str:
        """특징 하이라이트 HTML 생성"""
        
        # 톤에 따른 스타일 조정
        if tone == "luxury":
            container_style = "background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border: 1px solid #e0e0e0;"
            feature_style = "background: rgba(255,255,255,0.9); border-left: 4px solid #d4af37;"
        elif tone == "casual":
            container_style = "background: #f8f9fa; border: 1px solid #dee2e6;"
            feature_style = "background: white; border-left: 4px solid #28a745;"
        else:  # professional, friendly
            container_style = "background: #f8f9fa; border: 1px solid #dee2e6;"
            feature_style = "background: white; border-left: 4px solid #007bff;"
        
        feature_items = []
        for feature in features:
            feature_items.append(f'''
                <div style="padding: 12px; margin: 8px 0; {feature_style} border-radius: 4px;">
                    <span style="font-weight: 600; color: #333;">✓</span>
                    <span style="margin-left: 8px; color: #555;">{feature}</span>
                </div>
            ''')
        
        return f'''
        <div style="margin: 25px 0; padding: 20px; {container_style} border-radius: 8px;">
            <h4 style="margin: 0 0 15px 0; color: #333; font-size: 18px;">주요 특징</h4>
            <div>
                {"".join(feature_items)}
            </div>
        </div>
        '''

# 글로벌 인스턴스
html_flow = HtmlGenerationFlow()