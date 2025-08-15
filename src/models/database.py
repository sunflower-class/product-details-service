"""
SQLAlchemy Models for Template Management System
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Numeric, 
    ForeignKey, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
import os
from typing import Optional

Base = declarative_base()

class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'))
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    parent = relationship("Category", remote_side=[id], backref="children")
    templates = relationship("Template", back_populates="category")
    template_sets = relationship("TemplateSet", back_populates="category")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parent_id': self.parent_id,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TemplateStyle(Base):
    __tablename__ = 'template_styles'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    primary_color = Column(String(7), default='#4A90E2')
    secondary_color = Column(String(7), default='#7BB3F0')
    font_family = Column(String(200), default='Noto Sans KR, sans-serif')
    border_radius = Column(String(20), default='15px')
    shadow_style = Column(String(100), default='0 5px 15px rgba(0,0,0,0.08)')
    custom_css = Column(Text)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    templates = relationship("Template", back_populates="style")
    template_sets = relationship("TemplateSet", back_populates="style")
    
    def __repr__(self):
        return f"<TemplateStyle(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'font_family': self.font_family,
            'border_radius': self.border_radius,
            'shadow_style': self.shadow_style,
            'custom_css': self.custom_css,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Template(Base):
    __tablename__ = 'templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'))
    style_id = Column(Integer, ForeignKey('template_styles.id', ondelete='SET NULL'))
    block_type = Column(String(50), nullable=False)
    html_structure = Column(Text, nullable=False)
    css_styles = Column(Text)
    required_fields = Column(JSONB)
    example_data = Column(JSONB)
    thumbnail_url = Column(String(500))
    usage_count = Column(Integer, default=0)
    rating = Column(Numeric(3, 2), default=0.00)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="templates")
    style = relationship("TemplateStyle", back_populates="templates")
    variables = relationship("TemplateVariable", back_populates="template", cascade="all, delete-orphan")
    set_items = relationship("TemplateSetItem", back_populates="template")
    usage_history = relationship("TemplateUsageHistory", back_populates="template")
    user_templates = relationship("UserTemplate", back_populates="base_template")
    
    # Indexes
    __table_args__ = (
        Index('idx_templates_category', 'category_id'),
        Index('idx_templates_style', 'style_id'),
        Index('idx_templates_block_type', 'block_type'),
        Index('idx_templates_active', 'is_active'),
        Index('idx_templates_usage', 'usage_count'),
    )
    
    def __repr__(self):
        return f"<Template(id={self.id}, name='{self.name}', block_type='{self.block_type}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'style_id': self.style_id,
            'block_type': self.block_type,
            'html_structure': self.html_structure,
            'css_styles': self.css_styles,
            'required_fields': self.required_fields,
            'example_data': self.example_data,
            'thumbnail_url': self.thumbnail_url,
            'usage_count': self.usage_count,
            'rating': float(self.rating) if self.rating else 0.0,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TemplateSet(Base):
    __tablename__ = 'template_sets'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='SET NULL'))
    style_id = Column(Integer, ForeignKey('template_styles.id', ondelete='SET NULL'))
    thumbnail_url = Column(String(500))
    is_default = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="template_sets")
    style = relationship("TemplateStyle", back_populates="template_sets")
    items = relationship("TemplateSetItem", back_populates="template_set", cascade="all, delete-orphan")
    usage_history = relationship("TemplateUsageHistory", back_populates="template_set")
    
    # Indexes
    __table_args__ = (
        Index('idx_template_sets_category', 'category_id'),
        Index('idx_template_sets_featured', 'is_featured'),
    )
    
    def __repr__(self):
        return f"<TemplateSet(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'style_id': self.style_id,
            'thumbnail_url': self.thumbnail_url,
            'is_default': self.is_default,
            'is_featured': self.is_featured,
            'usage_count': self.usage_count,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TemplateSetItem(Base):
    __tablename__ = 'template_set_items'
    
    id = Column(Integer, primary_key=True)
    set_id = Column(Integer, ForeignKey('template_sets.id', ondelete='CASCADE'), nullable=False)
    template_id = Column(Integer, ForeignKey('templates.id', ondelete='CASCADE'), nullable=False)
    display_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template_set = relationship("TemplateSet", back_populates="items")
    template = relationship("Template", back_populates="set_items")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('set_id', 'template_id'),
        Index('idx_set_items_set', 'set_id'),
        Index('idx_set_items_order', 'display_order'),
    )
    
    def __repr__(self):
        return f"<TemplateSetItem(set_id={self.set_id}, template_id={self.template_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'set_id': self.set_id,
            'template_id': self.template_id,
            'display_order': self.display_order,
            'is_required': self.is_required,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class TemplateVariable(Base):
    __tablename__ = 'template_variables'
    
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey('templates.id', ondelete='CASCADE'), nullable=False)
    variable_name = Column(String(100), nullable=False)
    variable_type = Column(String(50), nullable=False)  # 'text', 'html', 'image', 'list', 'color'
    description = Column(Text)
    default_value = Column(Text)
    is_required = Column(Boolean, default=True)
    validation_rules = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("Template", back_populates="variables")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('template_id', 'variable_name'),
    )
    
    def __repr__(self):
        return f"<TemplateVariable(template_id={self.template_id}, name='{self.variable_name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'variable_name': self.variable_name,
            'variable_type': self.variable_type,
            'description': self.description,
            'default_value': self.default_value,
            'is_required': self.is_required,
            'validation_rules': self.validation_rules,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class UserTemplate(Base):
    __tablename__ = 'user_templates'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False)
    base_template_id = Column(Integer, ForeignKey('templates.id', ondelete='SET NULL'))
    name = Column(String(200), nullable=False)
    customizations = Column(JSONB)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    base_template = relationship("Template", back_populates="user_templates")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_templates_user', 'user_id'),
        Index('idx_user_templates_public', 'is_public'),
    )
    
    def __repr__(self):
        return f"<UserTemplate(id={self.id}, user_id='{self.user_id}', name='{self.name}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'base_template_id': self.base_template_id,
            'name': self.name,
            'customizations': self.customizations,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TemplateUsageHistory(Base):
    __tablename__ = 'template_usage_history'
    
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey('templates.id', ondelete='SET NULL'))
    template_set_id = Column(Integer, ForeignKey('template_sets.id', ondelete='SET NULL'))
    user_id = Column(String(100))
    product_info = Column(Text)
    generated_html = Column(Text)
    feedback_rating = Column(Integer)
    feedback_comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("Template", back_populates="usage_history")
    template_set = relationship("TemplateSet", back_populates="usage_history")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('feedback_rating >= 1 AND feedback_rating <= 5'),
        Index('idx_usage_history_template', 'template_id'),
        Index('idx_usage_history_user', 'user_id'),
        Index('idx_usage_history_date', 'created_at'),
    )
    
    def __repr__(self):
        return f"<TemplateUsageHistory(id={self.id}, template_id={self.template_id})>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'template_set_id': self.template_set_id,
            'user_id': self.user_id,
            'product_info': self.product_info,
            'generated_html': self.generated_html,
            'feedback_rating': self.feedback_rating,
            'feedback_comment': self.feedback_comment,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Database Connection and Session Management
class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            # Fallback for development
            self.database_url = "postgresql://user:password@localhost/product_details_db"
        
        self.engine = None
        self.SessionLocal = None
    
    def init_db(self):
        """Initialize database connection and create tables"""
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False  # Set to True for SQL debugging
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Create all tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session"""
        if not self.SessionLocal:
            self.init_db()
        
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()

# Global database manager instance
db_manager = DatabaseManager()

def get_db():
    """Dependency for FastAPI to get database session"""
    return next(db_manager.get_session())