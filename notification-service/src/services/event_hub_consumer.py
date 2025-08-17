"""
Azure Event Hubs Consumer 서비스
이벤트 허브에서 알림 이벤트를 수신하여 처리
"""
import asyncio
import json
import os
import logging
from typing import Dict, Any, List
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub import EventData, TransportType
from azure.eventhub.extensions.checkpointstoreblob import BlobCheckpointStore

from src.schemas.notification_event import NotificationEvent
from src.services.notification_dispatcher import NotificationDispatcher

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventHubConsumer:
    """Event Hub Consumer 서비스"""
    
    def __init__(self):
        self.connection_string = os.environ.get(
            "EVENTHUB_CONSUMER_CONNECTION_STRING",
            "Endpoint=sb://sangsangplus-eventhubs.servicebus.windows.net/;SharedAccessKeyName=NotificationConsumerKey;SharedAccessKey=mM9nLJ5gXwme9y0cJpoBbaUJXhF+39uZX+AEhEnx6Lw=;EntityPath=notification"
        )
        self.event_hub_name = os.environ.get(
            "NOTIFICATION_EVENTHUB_NAME",
            "notification"
        )
        self.consumer_group = os.environ.get(
            "EVENTHUB_CONSUMER_GROUP",
            "$Default"
        )
        
        # 체크포인트 스토어 설정
        storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        checkpoint_container = os.environ.get("CHECKPOINT_CONTAINER_NAME", "eventhub-checkpoints")
        
        self.checkpoint_store = None
        if storage_connection_string:
            try:
                self.checkpoint_store = BlobCheckpointStore.from_connection_string(
                    storage_connection_string, checkpoint_container
                )
                logger.info(f"✅ 체크포인트 스토어 초기화: {checkpoint_container}")
            except Exception as e:
                logger.error(f"❌ 체크포인트 스토어 실패: {e}")
        
        # 알림 발송기
        self.dispatcher = NotificationDispatcher()
        
        # 클라이언트 초기화
        self.client = None
        
    async def start_consuming(self):
        """Event Hub Consumer 시작"""
        logger.info(f"🚀 EventHub Consumer 시작: {self.event_hub_name}")
        
        try:
            # Event Hub Consumer Client 생성 (기본 AMQP 사용) - EntityPath 포함된 연결 문자열 사용
            self.client = EventHubConsumerClient.from_connection_string(
                conn_str=self.connection_string,
                consumer_group=self.consumer_group,
                checkpoint_store=self.checkpoint_store,
                logging_enable=True  # 디버깅용 상세 로깅 활성화
            )
            
            logger.info(f"✅ EventHub Consumer 연결: {self.event_hub_name}")
            
            async with self.client:
                # 이벤트 수신 시작
                await self.client.receive(
                    on_event=self._on_event_received,
                    on_error=self._on_error,
                    starting_position="-1"  # 가장 최근 이벤트부터 시작
                )
                
        except Exception as e:
            logger.error(f"❌ Event Hub Consumer 시작 실패: {e}", exc_info=True)
            raise
    
    async def _on_event_received(self, partition_context, event: EventData):
        """이벤트 수신 시 호출되는 콜백"""
        try:
            # 이벤트 데이터 파싱
            event_body = event.body_as_str()
            event_data = json.loads(event_body)
            
            # NotificationEvent 객체로 변환
            notification = NotificationEvent(**event_data)
            
            logger.info(f"📥 알림 수신: {notification.event_id} ({notification.user_id})")
            
            # 알림 발송 처리
            success = await self.dispatcher.dispatch_notification(notification)
            
            if success:
                logger.info(f"✅ 알림 발송 완료: {notification.event_id}")
                await partition_context.update_checkpoint(event)
            else:
                logger.warning(f"❌ 알림 발송 실패: {notification.event_id}")
            
        except Exception as e:
            logger.error(f"❌ 이벤트 처리 실패: {e}")
    
    async def _on_error(self, partition_context, error):
        """에러 발생 시 호출되는 콜백"""
        logger.error(f"❌ EventHub Consumer 에러: {error}")
    
    async def stop(self):
        """Consumer 중지"""
        logger.info("👋 EventHub Consumer 중지")
        if self.client:
            await self.client.close()
        if self.checkpoint_store:
            await self.checkpoint_store.close()

if __name__ == "__main__":
    consumer = EventHubConsumer()
    try:
        asyncio.run(consumer.start_consuming())
    except KeyboardInterrupt:
        asyncio.run(consumer.stop())