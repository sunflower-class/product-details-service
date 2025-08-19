"""
알림 발송기 - 다양한 채널로 알림 발송
"""
import asyncio
import json
import os
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime

from src.schemas.notification_event import NotificationEvent, MessageType
from src.core.redis_client import redis_store

class NotificationDispatcher:
    """알림 발송 처리기"""
    
    def __init__(self):
        # 개발팀용 알림 채널 설정 (선택사항)
        self.slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
        self.discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
        
        # 알림 로그 저장 여부
        self.save_logs = os.environ.get("SAVE_NOTIFICATION_LOGS", "true").lower() == "true"
        
    async def dispatch_notification(self, notification: NotificationEvent) -> bool:
        """알림을 적절한 채널로 발송"""
        
        try:
            # 알림 타입에 따른 발송 전략
            if notification.message_type == MessageType.SUCCESS:
                return await self._send_success_notification(notification)
            elif notification.message_type == MessageType.ERROR:
                return await self._send_error_notification(notification)
            elif notification.message_type == MessageType.PROGRESS:
                return await self._send_progress_notification(notification)
            else:
                return await self._send_general_notification(notification)
                
        except Exception as e:
            print(f"❌ 알림 발송 중 오류: {e}")
            return False
    
    async def _send_success_notification(self, notification: NotificationEvent) -> bool:
        """성공 알림 발송"""
        print(f"🎉 성공 알림 발송: {notification.title}")
        
        # Redis에 알림 저장 (필수)
        await self._save_to_redis(notification)
        
        # 로그 저장
        if self.save_logs:
            await self._save_notification_log(notification, "sent")
        
        return True
    
    async def _send_error_notification(self, notification: NotificationEvent) -> bool:
        """에러 알림 발송"""
        print(f"🚨 에러 알림 발송: {notification.title}")
        
        # Slack으로 에러 알림 (개발팀용)
        if self.slack_webhook:
            await self._send_slack_notification(notification)
        
        # Redis에 알림 저장 (필수)
        await self._save_to_redis(notification)
        
        # 로그 저장
        if self.save_logs:
            await self._save_notification_log(notification, "sent")
        
        return True
    
    async def _send_progress_notification(self, notification: NotificationEvent) -> bool:
        """진행상황 알림 발송"""
        print(f"⏳ 진행상황 알림 발송: {notification.title}")
        
        # 진행상황 알림도 Redis에 저장 및 실시간 브로드캐스트
        await self._save_to_redis(notification)
        return True
    
    async def _send_general_notification(self, notification: NotificationEvent) -> bool:
        """일반 알림 발송"""
        print(f"📢 일반 알림 발송: {notification.title}")
        
        # Redis에 저장 및 실시간 브로드캐스트
        await self._save_to_redis(notification)
        return True
    
    async def _send_slack_notification(self, notification: NotificationEvent) -> bool:
        """Slack으로 알림 발송 (개발팀용)"""
        if not self.slack_webhook:
            return True
        
        try:
            # Slack 메시지 포맷
            color = "good" if notification.message_type == MessageType.SUCCESS else "danger"
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{notification.service_type.upper()}] {notification.title}",
                        "text": notification.message,
                        "fields": [
                            {
                                "title": "사용자 ID",
                                "value": notification.user_id,
                                "short": True
                            },
                            {
                                "title": "이벤트 ID",
                                "value": notification.event_id,
                                "short": True
                            }
                        ],
                        "timestamp": int(notification.created_at.timestamp())
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    return response.status == 200
                    
        except Exception as e:
            print(f"❌ Slack 발송 중 오류: {e}")
            return False
    
    async def _save_to_redis(self, notification: NotificationEvent):
        """알림을 Redis에 저장"""
        try:
            notification_data = {
                "event_id": notification.event_id,
                "service_type": notification.service_type.value,
                "message_type": notification.message_type.value,
                "user_id": notification.user_id,
                "user_session": notification.user_session,
                "title": notification.title,
                "message": notification.message,
                "action_url": notification.action_url,
                "action_label": notification.action_label,
                "data_url": notification.data_url,
                "data_id": notification.data_id,
                "metadata": notification.metadata,
                "created_at": notification.created_at.isoformat()
            }
            
            await redis_store.save_notification(notification_data)
            
            # 실시간 알림 브로드캐스트
            await self._broadcast_realtime_notification(notification_data)
            
        except Exception as e:
            print(f"⚠️ Redis 저장 실패: {e}")

    async def _broadcast_realtime_notification(self, notification_data: dict):
        """실시간 알림 브로드캐스트"""
        try:
            user_id = notification_data.get("user_id")
            if user_id:
                await redis_store.publish_notification(user_id, notification_data)
                print(f"📡 실시간 알림 브로드캐스트: {user_id}")
        except Exception as e:
            print(f"❌ 실시간 알림 브로드캐스트 실패: {e}")

    async def _save_notification_log(self, notification: NotificationEvent, status: str):
        """알림 로그 저장 (파일 또는 DB)"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_id": notification.event_id,
                "service_type": notification.service_type,
                "message_type": notification.message_type,
                "user_id": notification.user_id,
                "title": notification.title,
                "status": status
            }
            
            # 간단히 파일로 저장 (실제로는 DB나 로깅 시스템 사용)
            log_file = "/app/logs/notifications.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\\n")
                
        except Exception as e:
            print(f"⚠️ 로그 저장 실패: {e}")