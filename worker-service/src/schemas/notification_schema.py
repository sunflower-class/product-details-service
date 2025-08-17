"""
범용 알림 서비스를 위한 메시지 스키마 정의
Worker 서비스에서 이벤트 허브로 알림 발송 시 사용
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

def create_success_notification(
    user_id: str,
    product_details_id: str,
    task_id: str,
    user_session: Optional[str] = None
) -> NotificationEvent:
    """HTML 생성 성공 알림 생성"""
    import os
    
    # 환경에 따른 product-details-service URL 설정
    base_url = os.environ.get("PRODUCT_DETAILS_SERVICE_URL", "https://api.buildingbite.com/product-details")
    
    return NotificationEvent(
        event_id=f"pd_success_{task_id}",
        service_type=ServiceType.PRODUCT_DETAILS,
        message_type=MessageType.SUCCESS,
        user_id=user_id,
        user_session=user_session,
        title="상품 상세페이지 생성 완료",
        message="상품 상세페이지가 성공적으로 생성되었습니다.",
        action_url=f"/product-details/{product_details_id}",
        action_label="결과 보기",
        data_url=f"{base_url}/api/generation/product-details/{product_details_id}",
        data_id=product_details_id,
        metadata={
            "task_id": task_id,
            "product_details_id": product_details_id,
            "result_api_url": f"{base_url}/api/generation/result/{task_id}"
        }
    )

def create_error_notification(
    user_id: str,
    task_id: str,
    error_message: str,
    user_session: Optional[str] = None
) -> NotificationEvent:
    """HTML 생성 실패 알림 생성"""
    import os
    
    # 환경에 따른 product-details-service URL 설정
    base_url = os.environ.get("PRODUCT_DETAILS_SERVICE_URL", "https://api.buildingbite.com/product-details")
    
    return NotificationEvent(
        event_id=f"pd_error_{task_id}",
        service_type=ServiceType.PRODUCT_DETAILS,
        message_type=MessageType.ERROR,
        user_id=user_id,
        user_session=user_session,
        title="상품 상세페이지 생성 실패",
        message=f"상품 상세페이지 생성 중 오류가 발생했습니다: {error_message}",
        action_url="/support",
        action_label="문의하기",
        data_url=f"{base_url}/api/generation/status/{task_id}",
        data_id=task_id,
        metadata={
            "task_id": task_id,
            "error": error_message
        }
    )

def create_progress_notification(
    user_id: str,
    task_id: str,
    progress_message: str,
    progress_percent: int,
    user_session: Optional[str] = None
) -> NotificationEvent:
    """HTML 생성 진행상황 알림 생성"""
    import os
    
    # 환경에 따른 product-details-service URL 설정
    base_url = os.environ.get("PRODUCT_DETAILS_SERVICE_URL", "https://api.buildingbite.com/product-details")
    
    return NotificationEvent(
        event_id=f"pd_progress_{task_id}_{progress_percent}",
        service_type=ServiceType.PRODUCT_DETAILS,
        message_type=MessageType.PROGRESS,
        user_id=user_id,
        user_session=user_session,
        title="상품 상세페이지 생성 중",
        message=progress_message,
        data_url=f"{base_url}/api/generation/status/{task_id}",
        data_id=task_id,
        metadata={
            "task_id": task_id,
            "progress_percent": progress_percent
        }
    )