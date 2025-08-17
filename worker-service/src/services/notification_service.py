"""
Worker 서비스에서 Azure Event Hubs로 알림을 발송하는 서비스
"""
import json
import os
from typing import Optional
from azure.eventhub import EventHubProducerClient, EventData, TransportType  # Add TransportType here
from azure.eventhub.exceptions import EventHubError

from src.schemas.notification_schema import NotificationEvent

class NotificationService:
    """알림 발송 서비스"""
    
    def __init__(self):
        self.connection_string = os.environ.get(
            "EVENTHUB_CONNECTION_STRING",
            "Endpoint=sb://sangsangplus-eventhubs.servicebus.windows.net/;SharedAccessKeyName=NotificationProducerKey;SharedAccessKey=9r2Q4Mx7bpO1IQJcZHrCz9R9e3m7Wq5Yq+AEhMONSSM=;EntityPath=notification"
        )
        self.event_hub_name = os.environ.get(
            "NOTIFICATION_EVENTHUB_NAME",
            "notification"
        )
        
        # Event Hub Producer 초기화
        self._init_producer()
    
    def _init_producer(self):
        """Event Hub Producer 초기화"""
        try:
            self.producer = EventHubProducerClient.from_connection_string(
                conn_str=self.connection_string
            )
            print(f"✅ EventHub Producer 연결: {self.event_hub_name}")
        except Exception as e:
            print(f"❌ EventHub Producer 실패: {e}")
            self.producer = None
    
    def send_notification(self, notification: NotificationEvent) -> bool:
        """알림 이벤트 발송"""
        if not self.producer:
            print("❌ EventHub Producer 미초기화")
            return False
        
        try:
            notification_data = notification.dict()
            
            if 'created_at' in notification_data and notification_data['created_at']:
                notification_data['created_at'] = notification_data['created_at'].isoformat()
            
            event_data = EventData(
                body=json.dumps(notification_data, ensure_ascii=False, default=str)
            )
            
            event_data_batch = self.producer.create_batch(partition_key=notification.user_id)
            event_data_batch.add(event_data)
            self.producer.send_batch(event_data_batch)
            
            print(f"📤 알림 발송: {notification.event_id} ({notification.user_id})")
            return True
            
        except EventHubError as e:
            print(f"❌ EventHub 발송 실패: {e}")
            return False
        except Exception as e:
            print(f"❌ 알림 발송 오류: {e}")
            return False
    
    def send_success_notification(
        self,
        user_id: str,
        product_details_id: str,
        task_id: str,
        user_session: Optional[str] = None
    ) -> bool:
        """성공 알림 발송"""
        from src.schemas.notification_schema import create_success_notification
        
        notification = create_success_notification(
            user_id=user_id,
            product_details_id=product_details_id,
            task_id=task_id,
            user_session=user_session
        )
        
        return self.send_notification(notification)
    
    def send_error_notification(
        self,
        user_id: str,
        task_id: str,
        error_message: str,
        user_session: Optional[str] = None
    ) -> bool:
        """실패 알림 발송"""
        from src.schemas.notification_schema import create_error_notification
        
        notification = create_error_notification(
            user_id=user_id,
            task_id=task_id,
            error_message=error_message,
            user_session=user_session
        )
        
        return self.send_notification(notification)
    
    def send_progress_notification(
        self,
        user_id: str,
        task_id: str,
        progress_message: str,
        progress_percent: int,
        user_session: Optional[str] = None
    ) -> bool:
        """진행상황 알림 발송"""
        from src.schemas.notification_schema import create_progress_notification
        
        notification = create_progress_notification(
            user_id=user_id,
            task_id=task_id,
            progress_message=progress_message,
            progress_percent=progress_percent,
            user_session=user_session
        )
        
        return self.send_notification(notification)
    
    def close(self):
        """Producer 종료"""
        if self.producer:
            self.producer.close()
            print("🔌 EventHub Producer 종료")

# 전역 인스턴스
notification_service = NotificationService()