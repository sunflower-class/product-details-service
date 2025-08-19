"""
ChromaDB 기반 템플릿 추천 서비스 (Worker 서비스용)
concept_style을 이용한 유사도 검색으로 적절한 HTML 템플릿을 추천
"""
import os
from typing import List, Dict, Optional, Any
import chromadb

class TemplateRecommendationService:
    """ChromaDB를 이용한 템플릿 추천 서비스"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = "product_templates"
        self._init_chromadb()
    
    def _init_chromadb(self):
        """ChromaDB 클라이언트 및 컬렉션 초기화"""
        try:
            # K8s 환경에서는 내부 서비스 DNS 사용
            host = 'chromadb.sangsangplus-backend.svc.cluster.local'
            port = 8000
            
            self.client = chromadb.HttpClient(host=host, port=port)
            self.collection = self.client.get_collection(self.collection_name)
            
            print(f"✅ ChromaDB 연결 성공: {self.collection_name} 컬렉션 ({self.collection.count()}개 템플릿)")
            
        except Exception as e:
            print(f"❌ ChromaDB 연결 실패: {e}")
            self.client = None
            self.collection = None
    
    def get_templates_by_product_info(
        self, 
        product_data: str,
        target_customer: str,
        tone: str,
        features: List[str],
        n_results: int = 2
    ) -> List[Dict[str, Any]]:
        """
        상품 정보를 분석하여 GPT에게 참고자료로 줄 템플릿들 추천
        
        Args:
            product_data: 상품 설명
            target_customer: 타겟 고객
            tone: 톤앤매너
            features: 주요 특징들
            n_results: 추천할 템플릿 수
            
        Returns:
            추천 템플릿 리스트 (GPT 참고용)
        """
        if not self.collection:
            print("⚠️ ChromaDB 연결되지 않음, 폴백 템플릿 사용")
            return self._get_fallback_templates()
        
        try:
            # 톤앤매너를 스타일 키워드로 매핑
            tone_style_map = {
                'professional': '전문적이고 신뢰할 수 있는 깔끔한',
                'casual': '편안하고 친근한 자연스러운',
                'friendly': '따뜻하고 부드러운 친근한',
                'luxury': '고급스럽고 프리미엄한 세련된',
                'playful': '활기차고 재미있는 다채로운',
                'serious': '진지하고 격식있는 깔끔한',
                'humorous': '유머러스하고 재치있는 재미있는'
            }
            
            style_keywords = tone_style_map.get(tone, '깔끔하고 현대적인')
            
            # 상품 특징을 포함한 쿼리 구성
            query_parts = [style_keywords]
            if features:
                # 처음 2개 특징만 사용하여 쿼리에 포함
                query_parts.extend(features[:2])
            
            search_query = ' '.join(query_parts)
            
            # 상품 카테고리 추정
            category = self._estimate_category(product_data)
            
            # ChromaDB 유사도 검색 - 더 많은 결과를 가져와서 필터링
            # 카테고리 필터 제거하여 더 넓은 범위에서 검색
            results = self.collection.query(
                query_texts=[search_query],
                n_results=max(n_results * 3, 10),  # 더 많은 결과를 가져옴
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 정리 (GPT 참고용 형태로)
            reference_templates = []
            if results and results['documents'] and results['documents'][0]:
                # 거리 기반으로 상위 결과만 선택 (거리가 작을수록 유사도 높음)
                for i, doc in enumerate(results['documents'][0][:n_results]):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    
                    # 거리가 너무 크면 스킵 (유사도가 너무 낮음)
                    # 임계값을 1.5로 설정 (기존보다 훨씬 관대함)
                    if distance > 1.5:
                        continue
                    
                    reference_templates.append({
                        'template_html': doc,
                        'concept_style': metadata.get('concept_style', ''),
                        'block_type': metadata.get('block_type', ''),
                        'category': metadata.get('category', ''),
                        'similarity_score': 1 - distance
                    })
            
            # 결과가 없으면 폴백 템플릿 사용
            if not reference_templates:
                print(f"⚠️ 유사한 템플릿을 찾지 못함, 폴백 템플릿 사용 (쿼리: '{search_query}')")
                return self._get_fallback_templates()
            
            print(f"🎯 템플릿 참고자료 추천 완료: {len(reference_templates)}개 (쿼리: '{search_query}')")
            return reference_templates
            
        except Exception as e:
            print(f"❌ 템플릿 추천 실패, 폴백 템플릿 사용: {e}")
            return self._get_fallback_templates()
    
    def _estimate_category(self, product_data: str) -> Optional[str]:
        """상품 설명에서 카테고리 추정"""
        category_keywords = {
            '생활용품': ['칫솔', '세제', '수건', '텀블러', '컵', '그릇', '청소', '위생'],
            '전자제품': ['헤드폰', '스피커', '충전기', '케이블', '폰', '태블릿', '블루투스', '무선'],
            '패션': ['옷', '바지', '셔츠', '신발', '가방', '지갑', '의류', '악세서리'],
            '화장품': ['크림', '로션', '마스크', '선크림', '립밤', '스킨케어', '뷰티']
        }
        
        product_data_lower = product_data.lower()
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in product_data_lower:
                    return category
        
        return None
    
    def _get_fallback_templates(self) -> List[Dict[str, Any]]:
        """폴백 템플릿 반환 (data.csv의 하드코딩된 템플릿)"""
        print("📌 폴백 템플릿 사용중...")
        
        # data.csv에서 가져온 기본 템플릿들
        fallback_templates = [
            {
                'template_html': "<div style='text-align: center; padding: 60px 20px; background-color: #ffffff;'><h2 style='font-family: 'Helvetica', sans-serif; font-weight: 300; font-size: 30px; color: #000; letter-spacing: 2px;'>PREMIUM PRODUCT</h2><h1 style='font-family: 'Times New Roman', serif; font-weight: bold; font-size: 48px; color: #000; margin-top: 5px;'>EXCEPTIONAL QUALITY</h1><hr style='width: 50px; border: 1px solid #000; margin: 30px auto;'/><p style='font-family: 'Noto Sans KR', sans-serif; font-size: 18px; color: #333;'>최고의 품질과 디자인을 만나보세요</p></div>",
                'concept_style': '세리프와 산세리프 폰트를 조화롭게 사용하여 고급스럽고 클래식한 분위기를 연출하는 인트로 스타일입니다.',
                'block_type': 'Introduction',
                'category': '생활용품'
            },
            {
                'template_html': "<div style='text-align: center; padding: 60px 20px; background-color: #f7f3f0;'><p style='font-family: 'Helvetica', sans-serif; font-size: 18px; color: #888;'>POINT 1</p><h3 style='font-family: 'Noto Sans KR', sans-serif; font-weight: bold; font-size: 36px; color: #333; margin-top: 10px;'>핵심 기능</h3><p style='font-family: 'Noto Sans KR', sans-serif; font-size: 16px; color: #555; margin-top: 20px; line-height: 1.6;'>제품의 가장 중요한 특징을<br>명확하고 간결하게 전달합니다.</p></div>",
                'concept_style': '제품의 핵심 특징을 POINT로 넘버링하여 순차적으로 설명하는 스타일입니다.',
                'block_type': 'KeyFeatures',
                'category': '생활용품'
            }
        ]
        
        return fallback_templates
    
    def health_check(self) -> bool:
        """ChromaDB 연결 상태 확인"""
        return self.client is not None and self.collection is not None
    
    def get_recommended_templates(
        self,
        style_query: str,
        block_type: str,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        고급 HTML 생성을 위한 템플릿 추천 (create_html_advanced.py용)
        
        Args:
            style_query: 스타일 콘셉트 쿼리
            block_type: 블록 타입
            n_results: 추천할 템플릿 수
            
        Returns:
            추천 템플릿 리스트
        """
        if not self.collection:
            print("⚠️ ChromaDB 연결되지 않음, 폴백 템플릿 사용")
            return self._get_fallback_templates()
        
        try:
            # ChromaDB 유사도 검색 - 더 많은 결과를 가져옴
            results = self.collection.query(
                query_texts=[style_query],
                n_results=max(n_results * 3, 10),
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 정리
            recommended_templates = []
            if results and results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0][:n_results]):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    
                    # 거리 임계값 체크 (1.5로 관대하게 설정)
                    if distance > 1.5:
                        continue
                    
                    recommended_templates.append({
                        'template_html': doc,
                        'concept_style': metadata.get('concept_style', ''),
                        'block_type': metadata.get('block_type', ''),
                        'category': metadata.get('category', ''),
                        'similarity_score': 1 - distance  # 거리를 유사도로 변환
                    })
            
            # 결과가 없으면 폴백 템플릿 사용
            if not recommended_templates:
                print(f"⚠️ 유사한 템플릿을 찾지 못함, 폴백 템플릿 사용 (쿼리: '{style_query[:50]}...')")
                return self._get_fallback_templates()
            
            print(f"🎯 스타일 매칭 템플릿 추천 완료: {len(recommended_templates)}개 (쿼리: '{style_query[:50]}...')")
            return recommended_templates
            
        except Exception as e:
            print(f"❌ 스타일 매칭 템플릿 추천 실패, 폴백 템플릿 사용: {e}")
            return self._get_fallback_templates()

# 전역 인스턴스
template_recommender = TemplateRecommendationService()