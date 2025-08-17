"""
Simplified SQLAlchemy Models for Template System
간단한 템플릿 나열 시스템용 모델
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, CheckConstraint, Index, Table, BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import List, Dict, Any
from contextlib import contextmanager

Base = declarative_base()

# Many-to-Many association table
template_categories = Table(
    'template_categories',
    Base.metadata,
    Column('template_id', Integer, ForeignKey('templates.id', ondelete='CASCADE'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True)
)

class Category(Base):
    """카테고리 (태그 역할)"""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    color = Column(String(7), default='#4A90E2')
    icon = Column(String(50))
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    templates = relationship("Template", secondary=template_categories, back_populates="categories")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'icon': self.icon,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Template(Base):
    """템플릿 (핵심 모델)"""
    __tablename__ = 'templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    preview_image = Column(String(500))
    block_type = Column(String(50), nullable=False)
    html_structure = Column(Text, nullable=False)
    
    # 스타일 정보
    primary_color = Column(String(7), default='#4A90E2')
    secondary_color = Column(String(7), default='#7BB3F0')
    
    # 메타데이터
    usage_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    difficulty_level = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    categories = relationship("Category", secondary=template_categories, back_populates="templates")
    usage_logs = relationship("TemplateUsageLog", back_populates="template")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('difficulty_level >= 1 AND difficulty_level <= 3'),
        Index('idx_templates_block_type', 'block_type'),
        Index('idx_templates_featured', 'is_featured'),
        Index('idx_templates_usage', 'usage_count'),
    )
    
    def __repr__(self):
        return f"<Template(id={self.id}, name='{self.name}', block_type='{self.block_type}')>"
    
    def to_dict(self, include_categories=True):
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'preview_image': self.preview_image,
            'block_type': self.block_type,
            'html_structure': self.html_structure,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'usage_count': self.usage_count,
            'is_featured': self.is_featured,
            'difficulty_level': self.difficulty_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_categories:
            result['categories'] = [cat.to_dict() for cat in self.categories]
        
        return result
    
    def get_category_names(self) -> List[str]:
        """카테고리 이름 리스트 반환"""
        return [cat.name for cat in self.categories]
    
    def get_difficulty_text(self) -> str:
        """난이도 텍스트 반환"""
        difficulty_map = {1: '쉬움', 2: '보통', 3: '어려움'}
        return difficulty_map.get(self.difficulty_level, '알 수 없음')

class TemplateUsageLog(Base):
    """템플릿 사용 로그"""
    __tablename__ = 'template_usage_log'
    
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey('templates.id', ondelete='SET NULL'))
    user_session = Column(String(100))
    product_info_hash = Column(String(64))
    feedback_rating = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("Template", back_populates="usage_logs")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('feedback_rating >= 1 AND feedback_rating <= 5'),
        Index('idx_usage_log_template', 'template_id'),
    )
    
    def __repr__(self):
        return f"<TemplateUsageLog(id={self.id}, template_id={self.template_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'user_session': self.user_session,
            'product_info_hash': self.product_info_hash,
            'feedback_rating': self.feedback_rating,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ProductDetails(Base):
    """생성된 상품 상세페이지"""
    __tablename__ = 'product_details'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer)  # 실제 상품 ID (나중에 연결)
    user_id = Column(String(100), nullable=False)  # 헤더 X-User-Id
    user_session = Column(String(100))  # 세션 ID (추가 정보)
    original_product_info = Column(Text, nullable=False)
    generated_html = Column(JSONB, nullable=False)  # 생성된 HTML 블록들
    used_templates = Column(ARRAY(Integer))  # 사용된 템플릿 ID들
    used_categories = Column(ARRAY(Integer))  # 사용된 카테고리 ID들
    status = Column(String(20), default='draft')  # 'draft', 'published', 'archived'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product_images = relationship("ProductImage", back_populates="product_details", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_product_details_product_id', 'product_id'),
        Index('idx_product_details_user_id', 'user_id'),
        Index('idx_product_details_session', 'user_session'),
    )
    
    def __repr__(self):
        return f"<ProductDetails(id={self.id}, product_id={self.product_id}, status='{self.status}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'user_id': self.user_id,
            'user_session': self.user_session,
            'original_product_info': self.original_product_info,
            'generated_html': self.generated_html,
            'used_templates': self.used_templates,
            'used_categories': self.used_categories,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ProductImage(Base):
    """상품 이미지 (생성/원본 포함)"""
    __tablename__ = 'product_images'
    
    id = Column(Integer, primary_key=True)
    product_details_id = Column(Integer, ForeignKey('product_details.id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer)  # 실제 상품 ID (선택적)
    user_id = Column(String(100), nullable=False)  # 헤더 X-User-Id
    original_prompt = Column(Text)  # GENERATED일 때만 필요
    translated_prompt = Column(Text)  # GENERATED일 때만 필요
    s3_url = Column(String(500))  # S3 URL
    temp_url = Column(String(500))  # Together AI 임시 URL 또는 원본 URL
    image_source = Column(String(20), default='GENERATED')  # 'GENERATED', 'ORIGINAL'
    image_type = Column(String(50), default='product')
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(BigInteger)
    is_uploaded_to_s3 = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    product_details = relationship("ProductDetails", back_populates="product_images")
    
    # Indexes
    __table_args__ = (
        Index('idx_product_images_product_details', 'product_details_id'),
        Index('idx_product_images_user_id', 'user_id'),
        Index('idx_product_images_product_id', 'product_id'),
    )
    
    def __repr__(self):
        return f"<ProductImage(id={self.id}, product_details_id={self.product_details_id}, image_source='{self.image_source}', image_type='{self.image_type}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'product_details_id': self.product_details_id,
            'product_id': self.product_id,
            'user_id': self.user_id,
            'original_prompt': self.original_prompt,
            'translated_prompt': self.translated_prompt,
            's3_url': self.s3_url,
            'temp_url': self.temp_url,
            'image_source': self.image_source,
            'image_type': self.image_type,
            'width': self.width,
            'height': self.height,
            'file_size': self.file_size,
            'is_uploaded_to_s3': self.is_uploaded_to_s3,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Database Manager (간소화된 버전)
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

class SimpleDatabaseManager:
    def __init__(self):
        self.database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://user:password@localhost:5432/product_details_db'
        )
        self.engine = None
        self.SessionLocal = None
    
    def init_db(self):
        """데이터베이스 초기화"""
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # 테이블 생성
        Base.metadata.create_all(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Generator:
        """세션 생성 (contextmanager)"""
        if not self.SessionLocal:
            self.init_db()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

# 글로벌 인스턴스
simple_db = SimpleDatabaseManager()

def get_db():
    """FastAPI dependency"""
    return next(simple_db.get_session())