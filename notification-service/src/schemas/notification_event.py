"""
알림 이벤트 스키마 정의 (Worker 서비스와 동일)
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class ServiceType(str, Enum):
    """서비스 타입 정의"""
    PRODUCT_DETAILS = "product-details"
    USER_SERVICE = "user-service"
    REVIEW_SERVICE = "review-service"
    CUSTOMER_SERVICE = "customer-service"

class MessageType(str, Enum):
    """메시지 타입 정의"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PROGRESS = "progress"

class NotificationEvent(BaseModel):
    """표준 알림 이벤트 구조"""
    
    # 기본 식별 정보
    event_id: str = Field(..., description="고유 이벤트 ID")
    service_type: ServiceType = Field(..., description="알림을 발송하는 서비스")
    message_type: MessageType = Field(..., description="메시지 타입")
    
    # 사용자 정보
    user_id: str = Field(..., description="알림 수신 대상 사용자 ID")
    user_session: Optional[str] = Field(None, description="사용자 세션 ID")
    
    # 메시지 내용
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지 내용")
    
    # 액션 정보
    action_url: Optional[str] = Field(None, description="클릭 시 이동할 URL")
    action_label: Optional[str] = Field(None, description="액션 버튼 라벨")
    
    # 데이터 정보
    data_url: Optional[str] = Field(None, description="관련 데이터 API URL")
    data_id: Optional[str] = Field(None, description="관련 데이터 ID")
    
    # 추가 메타데이터
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 메타데이터")
    
    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.utcnow, description="이벤트 생성 시간")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }