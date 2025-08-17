"""
Database configuration and connection management
"""
import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.models.database import Base, db_manager

# Database configuration
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://user:password@localhost:5432/product_details_db'
)

# Development SQLite fallback
if not DATABASE_URL.startswith('postgresql'):
    DATABASE_URL = 'sqlite:///./product_details.db'

def init_database():
    """Initialize database connection and create tables"""
    try:
        db_manager.database_url = DATABASE_URL
        db_manager.init_db()
        print(f"✅ Database initialized successfully: {DATABASE_URL}")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session
    Usage: db: Session = Depends(get_db_session)
    """
    session = next(db_manager.get_session())
    try:
        yield session
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database session
    Usage: 
    with get_db_context() as db:
        result = db.query(Template).all()
    """
    session = next(db_manager.get_session())
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=db_manager.engine)
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        return False

def drop_tables():
    """Drop all database tables (for development only)"""
    try:
        Base.metadata.drop_all(bind=db_manager.engine)
        print("⚠️ All database tables dropped")
        return True
    except Exception as e:
        print(f"❌ Failed to drop tables: {e}")
        return False

def check_db_connection() -> bool:
    """Check if database connection is working"""
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
        print("✅ Database connection is working")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False