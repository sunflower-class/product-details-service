"""
이미지 생성 및 저장 관리 서비스
S3 업로드와 데이터베이스 저장을 담당
"""
import os
import time
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from src.services.create_image import create_image, reshape_image, translate_prompt
from src.models.models_simple import ProductImage, ProductDetails
from src.models.models_simple import simple_db

class ImageManager:
    def __init__(self):
        self.s3_available = self._check_s3_config()
    
    def _check_s3_config(self) -> bool:
        """S3 설정이 되어 있는지 확인"""
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        s3_bucket = os.getenv('S3_BUCKET_NAME')
        
        return all([aws_access_key, aws_secret_key, s3_bucket])
    
    def generate_and_store_image(
        self,
        product_details_id: int,
        prompt: str,
        user_id: str,
        image_type: str = 'product',
        reference_url: Optional[str] = None,
        product_id: Optional[int] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        이미지를 생성하고 저장합니다.
        
        Args:
            product_details_id: 상품 상세 ID
            prompt: 이미지 생성 프롬프트
            image_type: 이미지 타입 ('product', 'background', 'icon', etc.)
            reference_url: 참조 이미지 URL (reshape용)
            product_id: 실제 상품 ID (선택적)
            timeout: API 호출 타임아웃 (초)
        
        Returns:
            이미지 정보 딕셔너리 (에러 시 error 키 포함)
        """
        
        try:
            print(f"🎨 이미지 생성 시작: {prompt[:50]}...")
            
            # 1. 프롬프트 번역
            try:
                translated_prompt = translate_prompt(prompt)
                print(f"📝 프롬프트 번역 완료: {translated_prompt[:50]}...")
            except Exception as e:
                print(f"⚠️ 프롬프트 번역 실패, 원본 사용: {e}")
                translated_prompt = prompt
            
            # 2. 이미지 생성 (타임아웃 적용)
            response = None
            try:
                if reference_url and prompt.startswith("product:"):
                    # 기존 상품 이미지 변형
                    clean_prompt = prompt[8:].strip()
                    response = reshape_image(clean_prompt, reference_url, timeout=timeout)
                else:
                    # 새 이미지 생성
                    response = create_image(prompt, timeout=timeout)
                    
            except TimeoutError as e:
                print(f"⏰ 이미지 생성 타임아웃: {e}")
                return {
                    'error': f'Image generation timeout after {timeout}s',
                    'prompt': prompt,
                    'image_type': image_type
                }
            except Exception as e:
                print(f"❌ 이미지 생성 API 오류: {e}")
                return {
                    'error': f'Image generation API error: {str(e)}',
                    'prompt': prompt,
                    'image_type': image_type
                }
            
            # 3. 응답 검증
            if not response or not response.data or len(response.data) == 0:
                print("❌ 이미지 생성 API 응답 없음")
                return {
                    'error': 'No response from image generation API',
                    'prompt': prompt,
                    'image_type': image_type
                }
            
            temp_url = response.data[0].url
            if not temp_url:
                print("❌ 이미지 URL이 응답에 없음")
                return {
                    'error': 'No image URL in API response',
                    'prompt': prompt,
                    'image_type': image_type
                }
            
            print(f"✅ 이미지 생성 성공: {temp_url}")
            
            # 4. 데이터베이스에 저장 (재시도 로직 포함)
            with simple_db.get_session() as db:
                # product_details_id 존재 확인 및 재시도
                max_retries = 3
                retry_delay = 1  # 1초
                
                for attempt in range(max_retries):
                    try:
                        # product_details 존재 확인
                        existing_details = db.query(ProductDetails).filter(
                            ProductDetails.id == product_details_id
                        ).first()
                        
                        if existing_details:
                            # 존재하면 이미지 레코드 생성
                            image_record = ProductImage(
                                product_details_id=product_details_id,
                                product_id=product_id,
                                user_id=user_id,
                                original_prompt=prompt,
                                translated_prompt=translated_prompt,
                                temp_url=temp_url,
                                image_source='GENERATED',
                                image_type=image_type,
                                is_uploaded_to_s3=False
                            )
                            
                            db.add(image_record)
                            db.flush()  # ID 생성을 위해
                            break  # 성공하면 루프 종료
                            
                        else:
                            print(f"⏳ ProductDetails ID {product_details_id} 찾을 수 없음. 재시도 {attempt + 1}/{max_retries}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                retry_delay *= 2  # 지수적 백오프
                                continue
                            else:
                                # 최대 재시도 횟수 초과
                                print(f"❌ ProductDetails ID {product_details_id} 최종 실패 - 레코드가 존재하지 않음")
                                return {
                                    'error': f'ProductDetails with ID {product_details_id} does not exist after {max_retries} attempts',
                                    'prompt': prompt,
                                    'image_type': image_type
                                }
                                
                    except Exception as e:
                        if "ForeignKeyViolation" in str(e) or "foreign key constraint" in str(e).lower():
                            print(f"⏳ 외래 키 제약 조건 위반, 재시도 {attempt + 1}/{max_retries}: {e}")
                            if attempt < max_retries - 1:
                                db.rollback()  # 트랜잭션 롤백
                                time.sleep(retry_delay)
                                retry_delay *= 2  # 지수적 백오프
                                continue
                            else:
                                raise  # 최대 재시도 후에도 실패하면 예외 발생
                        else:
                            raise  # 다른 종류의 예외는 즉시 발생
                
                image_id = image_record.id
                
                # 5. S3 업로드 (설정되어 있다면)
                if self.s3_available:
                    try:
                        s3_url = self._upload_to_s3(temp_url, image_id, image_type)
                        if s3_url:
                            image_record.s3_url = s3_url
                            image_record.is_uploaded_to_s3 = True
                            print(f"☁️ S3 업로드 완료: {s3_url}")
                        else:
                            print(f"⚠️ S3 업로드 실패, 임시 URL 사용: {temp_url}")
                    except Exception as e:
                        print(f"⚠️ S3 업로드 중 오류 (임시 URL 사용): {e}")
                
                return {
                    'id': image_record.id,
                    'url': image_record.s3_url if image_record.s3_url else temp_url,
                    'temp_url': temp_url,
                    's3_url': image_record.s3_url,
                    'is_uploaded_to_s3': image_record.is_uploaded_to_s3,
                    'image_type': image_type,
                    'prompt': prompt
                }
                
        except Exception as e:
            print(f"❌ 이미지 생성 전체 프로세스 실패: {e}")
            return {
                'error': f'Complete image generation process failed: {str(e)}',
                'prompt': prompt,
                'image_type': image_type
            }
    
    def _upload_to_s3(self, temp_url: str, image_id: int, image_type: str) -> Optional[str]:
        """
        임시 URL의 이미지를 S3에 업로드합니다.
        S3 설정이 완료되면 구현
        """
        try:
            import boto3
            import requests
            from datetime import datetime
            
            # 1. 임시 URL에서 이미지 다운로드
            print(f"📥 이미지 다운로드 중: {temp_url}")
            try:
                response = requests.get(temp_url, timeout=30)
                if response.status_code != 200:
                    print(f"❌ 이미지 다운로드 실패: HTTP {response.status_code}")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"❌ 이미지 다운로드 네트워크 오류: {e}")
                return None
            except Exception as e:
                print(f"❌ 이미지 다운로드 실패: {e}")
                return None

            # 2. S3 클라이언트 생성
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
            )

            # 3. S3에 업로드
            bucket = os.getenv('S3_BUCKET_NAME')
            s3_key = f"product-images/{image_type}/{image_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            print(f"📤 S3 업로드 중: {bucket}/{s3_key}")
            # 버킷 정책으로 public 접근이 설정되어 있으므로 ACL 불필요
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=response.content,
                ContentType='image/jpeg'
            )
            
            # 4. S3 URL 반환 (public-read ACL로 직접 접근 가능)
            s3_url = f"https://{bucket}.s3.amazonaws.com/{s3_key}"
            print(f"✅ S3 업로드 완료: {s3_url}")
            return s3_url

        except Exception as e:
            print(f"❌ S3 업로드 실패: {e}")
            return None
    
    def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        """ID로 이미지 정보를 조회합니다."""
        with simple_db.get_session() as db:
            image = db.query(ProductImage).filter(ProductImage.id == image_id).first()
            if image:
                return {
                    'id': image.id,
                    'url': image.s3_url if image.s3_url else image.temp_url,
                    'temp_url': image.temp_url,
                    's3_url': image.s3_url,
                    'is_uploaded_to_s3': image.is_uploaded_to_s3,
                    'image_type': image.image_type,
                    'prompt': image.original_prompt
                }
        return None
    
    def get_images_by_product_details(self, product_details_id: int) -> List[Dict[str, Any]]:
        """상품 상세 ID로 관련 이미지들을 조회합니다."""
        with simple_db.get_session() as db:
            images = db.query(ProductImage).filter(
                ProductImage.product_details_id == product_details_id
            ).all()
            
            return [
                {
                    'id': img.id,
                    'url': img.s3_url if img.s3_url else img.temp_url,
                    'temp_url': img.temp_url,
                    's3_url': img.s3_url,
                    'is_uploaded_to_s3': img.is_uploaded_to_s3,
                    'image_type': img.image_type,
                    'prompt': img.original_prompt
                }
                for img in images
            ]
    
    def batch_upload_to_s3(self, limit: int = 50) -> int:
        """
        S3에 업로드되지 않은 이미지들을 배치로 업로드합니다.
        
        Returns:
            업로드 성공한 이미지 수
        """
        if not self.s3_available:
            print("⚠️ S3 설정이 완료되지 않았습니다.")
            return 0
        
        with simple_db.get_session() as db:
            # S3에 업로드되지 않은 이미지들 조회
            pending_images = db.query(ProductImage).filter(
                ProductImage.is_uploaded_to_s3 == False,
                ProductImage.temp_url.isnot(None)
            ).limit(limit).all()
            
            success_count = 0
            
            for image in pending_images:
                try:
                    s3_url = self._upload_to_s3(image.temp_url, image.id, image.image_type)
                    if s3_url:
                        image.s3_url = s3_url
                        image.is_uploaded_to_s3 = True
                        success_count += 1
                        print(f"✅ 이미지 {image.id} S3 업로드 완료")
                    
                except Exception as e:
                    print(f"❌ 이미지 {image.id} S3 업로드 실패: {e}")
            
            db.commit()
            
            print(f"📊 배치 업로드 완료: {success_count}/{len(pending_images)}")
            return success_count

# 글로벌 인스턴스
image_manager = ImageManager()