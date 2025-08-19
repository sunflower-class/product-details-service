"""
ChromaDB 기반 템플릿 추천 서비스
concept_style을 이용한 유사도 검색으로 적절한 HTML 템플릿을 추천
"""
import os
from typing import List, Dict, Optional, Any
import chromadb
from chromadb.config import Settings

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
            
            # 개발 환경에서는 localhost 사용 (포트포워딩)
            if os.getenv('ENVIRONMENT', 'production') == 'development':
                host = 'localhost'
            
            self.client = chromadb.HttpClient(host=host, port=port)
            self.collection = self.client.get_collection(self.collection_name)
            
            print(f"✅ ChromaDB 연결 성공: {self.collection_name} 컬렉션 ({self.collection.count()}개 템플릿)")
            
        except Exception as e:
            print(f"❌ ChromaDB 연결 실패: {e}")
            self.client = None
            self.collection = None
    
    def get_recommended_templates(
        self, 
        style_query: str,
        block_type: Optional[str] = None,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        스타일 쿼리를 기반으로 유사한 템플릿들을 추천
        
        Args:
            style_query: 찾고자 하는 스타일 설명 (예: "깔끔하고 현대적인")
            block_type: 특정 블록 타입 필터링 (예: "Introduction", "KeyFeatures")
            category: 특정 카테고리 필터링 (예: "생활용품")
            n_results: 반환할 결과 수
            
        Returns:
            추천 템플릿 리스트
        """
        if not self.collection:
            print("❌ ChromaDB 연결되지 않음")
            return []
        
        try:
            # 필터 조건 구성
            where_filter = {}
            if block_type:
                where_filter['block_type'] = block_type
            if category:
                where_filter['category'] = category
            
            # concept_style 기반 유사도 검색
            results = self.collection.query(
                query_texts=[style_query],
                where=where_filter if where_filter else None,
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 정리
            recommendations = []
            if results and results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i]
                    
                    recommendations.append({
                        'template_html': doc,
                        'block_type': metadata.get('block_type'),
                        'category': metadata.get('category'),
                        'concept_style': metadata.get('concept_style'),
                        'similarity_score': 1 - distance,  # 거리를 유사도로 변환
                        'template_id': results['ids'][0][i] if results['ids'] else None
                    })
            
            print(f"🔍 템플릿 추천 완료: {len(recommendations)}개 (쿼리: '{style_query}')")
            return recommendations
            
        except Exception as e:
            print(f"❌ 템플릿 추천 실패: {e}")
            return []
    
    def get_templates_by_product_info(
        self, 
        product_data: str,
        target_customer: str,
        tone: str,
        features: List[str],
        n_results: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        상품 정보를 분석하여 각 블록 타입별로 적절한 템플릿 추천
        
        Args:
            product_data: 상품 설명
            target_customer: 타겟 고객
            tone: 톤앤매너
            features: 주요 특징들
            n_results: 각 블록 타입별 추천 수
            
        Returns:
            블록 타입별 추천 템플릿 딕셔너리
        """
        if not self.collection:
            return {}
        
        # 톤앤매너를 스타일 키워드로 매핑
        tone_style_map = {
            'professional': '전문적이고 신뢰할 수 있는',
            'casual': '편안하고 친근한',
            'friendly': '따뜻하고 부드러운',
            'luxury': '고급스럽고 프리미엄한',
            'playful': '활기차고 재미있는',
            'serious': '진지하고 격식있는',
            'humorous': '유머러스하고 재치있는'
        }
        
        base_style = tone_style_map.get(tone, '깔끔하고 현대적인')
        
        # 상품 카테고리 추정 (간단한 키워드 매칭)
        category = self._estimate_category(product_data)
        
        recommendations = {}
        
        # Introduction 블록 추천
        intro_query = f"{base_style} 제품 소개"
        recommendations['Introduction'] = self.get_recommended_templates(
            style_query=intro_query,
            block_type='Introduction',
            category=category,
            n_results=n_results
        )
        
        # KeyFeatures 블록 추천
        features_query = f"{base_style} 제품 특징"
        if features:
            features_query += f" {' '.join(features[:2])}"  # 처음 2개 특징만 사용
        
        recommendations['KeyFeatures'] = self.get_recommended_templates(
            style_query=features_query,
            block_type='KeyFeatures', 
            category=category,
            n_results=n_results
        )
        
        # Specifications 블록 추천 (필요시)
        spec_query = f"{base_style} 제품 사양"
        recommendations['Specifications'] = self.get_recommended_templates(
            style_query=spec_query,
            block_type='Specifications',
            category=category,
            n_results=min(2, n_results)  # 사양은 적게
        )
        
        print(f"🎯 상품별 템플릿 추천 완료: {sum(len(v) for v in recommendations.values())}개")
        return recommendations
    
    def _estimate_category(self, product_data: str) -> Optional[str]:
        """상품 설명에서 카테고리 추정"""
        category_keywords = {
            '생활용품': ['칫솔', '세제', '수건', '텀블러', '컵', '그릇'],
            '전자제품': ['헤드폰', '스피커', '충전기', '케이블', '폰', '태블릿'],
            '패션': ['옷', '바지', '셔츠', '신발', '가방', '지갑'],
            '화장품': ['크림', '로션', '마스크', '선크림', '립밤']
        }
        
        product_data_lower = product_data.lower()
        
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in product_data_lower:
                    return category
        
        return None
    
    def health_check(self) -> bool:
        """ChromaDB 연결 상태 확인"""
        try:
            if self.collection:
                count = self.collection.count()
                return count > 0
        except:
            pass
        return False

# 전역 인스턴스
template_recommender = TemplateRecommendationService()