"""
Product CRUD 서비스
상품 데이터의 생성, 조회, 수정, 삭제 관리
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from src.models.models_simple import Product, ProductDetails
from src.core.database import get_db_context


class ProductService:
    """Product CRUD 서비스"""

    @staticmethod
    def create_product(
        product_data: Dict[str, Any],
        user_id: str,
        user_session: Optional[str] = None
    ) -> Product:
        """새 상품 생성"""
        with get_db_context() as db:
            product = Product(
                name=product_data.get('name'),
                description=product_data.get('description'),
                category=product_data.get('category'),
                brand=product_data.get('brand'),
                price=product_data.get('price'),
                currency=product_data.get('currency', 'KRW'),
                original_product_data=product_data.get('original_product_data', ''),
                main_image_url=product_data.get('main_image_url'),
                features=product_data.get('features'),
                target_customer=product_data.get('target_customer'),
                tone=product_data.get('tone'),
                status=product_data.get('status', 'active'),
                is_published=product_data.get('is_published', False),
                user_id=user_id,
                user_session=user_session
            )
            
            db.add(product)
            db.flush()  # ID 생성을 위해 flush
            db.refresh(product)
            
            # 세션에서 분리하여 반환 (DetachedInstanceError 방지)
            db.expunge(product)
            return product

    @staticmethod
    def get_product_by_id(product_id: int, user_id: Optional[str] = None) -> Optional[Product]:
        """ID로 상품 조회"""
        with get_db_context() as db:
            query = db.query(Product).options(joinedload(Product.product_details))
            
            if user_id:
                # 사용자가 지정된 경우 해당 사용자의 상품만 조회
                query = query.filter(
                    and_(Product.id == product_id, Product.user_id == user_id)
                )
            else:
                # 관리자용: 모든 상품 조회 가능
                query = query.filter(Product.id == product_id)
            
            return query.first()

    @staticmethod
    def get_products(
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        is_published: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[Product]:
        """상품 목록 조회 (필터링 및 페이징 지원)"""
        with get_db_context() as db:
            query = db.query(Product).options(joinedload(Product.product_details))
            
            # 필터 적용
            if user_id:
                query = query.filter(Product.user_id == user_id)
            
            if status:
                query = query.filter(Product.status == status)
            
            if category:
                query = query.filter(Product.category == category)
            
            if is_published is not None:
                query = query.filter(Product.is_published == is_published)
            
            if search:
                # 상품명, 설명, 브랜드에서 검색
                search_filter = or_(
                    Product.name.ilike(f'%{search}%'),
                    Product.description.ilike(f'%{search}%'),
                    Product.brand.ilike(f'%{search}%')
                )
                query = query.filter(search_filter)
            
            # 정렬 및 페이징
            return query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def update_product(
        product_id: int,
        product_data: Dict[str, Any],
        user_id: str
    ) -> Optional[Product]:
        """상품 정보 업데이트"""
        with get_db_context() as db:
            product = db.query(Product).filter(
                and_(Product.id == product_id, Product.user_id == user_id)
            ).first()
            
            if not product:
                return None
            
            # 업데이트 가능한 필드들
            updateable_fields = [
                'name', 'description', 'category', 'brand', 'price', 'currency',
                'original_product_data', 'main_image_url', 'features', 
                'target_customer', 'tone', 'status', 'is_published'
            ]
            
            for field in updateable_fields:
                if field in product_data:
                    setattr(product, field, product_data[field])
            
            # published_at 자동 설정
            if 'is_published' in product_data:
                if product_data['is_published'] and not product.published_at:
                    from datetime import datetime
                    product.published_at = datetime.utcnow()
                elif not product_data['is_published']:
                    product.published_at = None
            
            db.refresh(product)
            return product

    @staticmethod
    def delete_product(product_id: int, user_id: str) -> bool:
        """상품 삭제 (연관된 product_details도 자동 삭제)"""
        with get_db_context() as db:
            product = db.query(Product).filter(
                and_(Product.id == product_id, Product.user_id == user_id)
            ).first()
            
            if not product:
                return False
            
            # CASCADE 옵션으로 product_details도 자동 삭제됨
            db.delete(product)
            return True

    @staticmethod
    def get_product_with_details(product_id: int, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """상품과 연관된 상세페이지들을 함께 조회"""
        product = ProductService.get_product_by_id(product_id, user_id)
        
        if not product:
            return None
        
        product_dict = product.to_dict()
        product_dict['product_details'] = [detail.to_dict() for detail in product.product_details]
        product_dict['product_details_count'] = len(product.product_details)
        
        return product_dict

    @staticmethod
    def get_product_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
        """상품 통계 정보"""
        with get_db_context() as db:
            query = db.query(Product)
            
            if user_id:
                query = query.filter(Product.user_id == user_id)
            
            total_products = query.count()
            active_products = query.filter(Product.status == 'active').count()
            published_products = query.filter(Product.is_published == True).count()
            
            # 카테고리별 통계
            categories = db.execute("""
                SELECT category, COUNT(*) as count 
                FROM products 
                {} 
                GROUP BY category 
                ORDER BY count DESC
            """.format("WHERE user_id = :user_id" if user_id else ""), 
            {'user_id': user_id} if user_id else {}
            ).fetchall()
            
            return {
                'total_products': total_products,
                'active_products': active_products,
                'published_products': published_products,
                'categories': [{'category': cat[0], 'count': cat[1]} for cat in categories]
            }

    @staticmethod
    def increase_view_count(product_id: int) -> bool:
        """상품 조회수 증가"""
        with get_db_context() as db:
            product = db.query(Product).filter(Product.id == product_id).first()
            
            if product:
                product.view_count += 1
                return True
            
            return False