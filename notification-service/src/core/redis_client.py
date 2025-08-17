"""
Redis 클라이언트 - 알림 저장 및 관리
"""
import os
import json
import asyncio
from typing import List, Dict, Optional, Any
import redis.asyncio as aioredis
from datetime import datetime, timedelta


class RedisNotificationStore:
    """Redis 기반 알림 저장소"""
    
    def __init__(self):
        self.redis = None
        self._init_redis()
    
    def _init_redis(self):
        """Redis 연결 초기화"""
        try:
            # worker-service와 동일한 Redis 설정 사용
            host = os.getenv('REDIS_HOST', 'localhost')
            port = int(os.getenv('REDIS_PORT', '6379'))
            password = os.getenv('REDIS_PASSWORD')
            ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
            
            self.redis = aioredis.Redis(
                host=host,
                port=port,
                password=password,
                ssl=ssl,
                decode_responses=True
            )
            print(f"✅ Redis 연결 초기화: {host}:{port}")
            
        except Exception as e:
            print(f"❌ Redis 연결 실패: {e}")
            self.redis = None
    
    async def save_notification(self, notification_data: Dict[str, Any]) -> bool:
        """알림을 Redis에 저장"""
        if not self.redis:
            return False
            
        try:
            notification_id = notification_data['event_id']
            user_id = notification_data['user_id']
            
            # 1. 알림 상세 정보 저장
            notification_key = f"notification:{notification_id}"
            notification_data['status'] = 'unread'
            notification_data['created_at'] = datetime.now().isoformat()
            
            await self.redis.setex(
                notification_key, 
                timedelta(days=30).total_seconds(),  # 30일 후 자동 삭제
                json.dumps(notification_data, ensure_ascii=False)
            )
            
            # 2. 사용자별 알림 목록에 추가
            user_notifications_key = f"notifications:user:{user_id}"
            await self.redis.lpush(user_notifications_key, notification_id)
            
            # 3. 사용자별 목록도 30일 TTL 설정
            await self.redis.expire(user_notifications_key, timedelta(days=30))
            
            # 4. 최대 100개 알림만 유지 (오래된 것 삭제)
            await self.redis.ltrim(user_notifications_key, 0, 99)
            
            print(f"✅ 알림 저장: {notification_id} for {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ 알림 저장 실패: {e}")
            return False
    
    async def get_user_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """사용자의 알림 목록 조회"""
        if not self.redis:
            return []
            
        try:
            user_notifications_key = f"notifications:user:{user_id}"
            
            # 알림 ID 목록 조회 (최신순)
            notification_ids = await self.redis.lrange(
                user_notifications_key, 
                offset, 
                offset + limit - 1
            )
            
            if not notification_ids:
                return []
            
            # 각 알림의 상세 정보 조회
            notifications = []
            for notification_id in notification_ids:
                notification_key = f"notification:{notification_id}"
                notification_data = await self.redis.get(notification_key)
                
                if notification_data:
                    notifications.append(json.loads(notification_data))
            
            return notifications
            
        except Exception as e:
            print(f"❌ 알림 조회 실패: {e}")
            return []
    
    async def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """알림을 읽음으로 표시"""
        if not self.redis:
            return False
            
        try:
            notification_key = f"notification:{notification_id}"
            notification_data = await self.redis.get(notification_key)
            
            if not notification_data:
                return False
            
            data = json.loads(notification_data)
            
            # 사용자 확인
            if data.get('user_id') != user_id:
                return False
            
            # 읽음 상태 업데이트
            data['status'] = 'read'
            data['read_at'] = datetime.now().isoformat()
            
            await self.redis.setex(
                notification_key,
                timedelta(days=30).total_seconds(),
                json.dumps(data, ensure_ascii=False)
            )
            
            print(f"✅ 알림 읽음 처리: {notification_id}")
            return True
            
        except Exception as e:
            print(f"❌ 알림 읽음 처리 실패: {e}")
            return False
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """알림 삭제"""
        if not self.redis:
            return False
            
        try:
            # 1. 알림 존재 및 권한 확인
            notification_key = f"notification:{notification_id}"
            notification_data = await self.redis.get(notification_key)
            
            if not notification_data:
                return False
            
            data = json.loads(notification_data)
            if data.get('user_id') != user_id:
                return False
            
            # 2. 사용자 알림 목록에서 제거
            user_notifications_key = f"notifications:user:{user_id}"
            await self.redis.lrem(user_notifications_key, 1, notification_id)
            
            # 3. 알림 상세 정보 삭제
            await self.redis.delete(notification_key)
            
            print(f"✅ 알림 삭제: {notification_id}")
            return True
            
        except Exception as e:
            print(f"❌ 알림 삭제 실패: {e}")
            return False
    
    async def get_unread_count(self, user_id: str) -> int:
        """사용자의 읽지 않은 알림 개수"""
        if not self.redis:
            return 0
            
        try:
            notifications = await self.get_user_notifications(user_id, limit=100)
            unread_count = sum(1 for n in notifications if n.get('status') == 'unread')
            return unread_count
            
        except Exception as e:
            print(f"❌ 미읽음 개수 조회 실패: {e}")
            return 0

    async def publish_notification(self, user_id: str, notification_data: Dict[str, Any]):
        """실시간 알림을 pub/sub으로 브로드캐스트"""
        if not self.redis:
            return
            
        try:
            channel = f"notifications:user:{user_id}"
            await self.redis.publish(
                channel, 
                json.dumps(notification_data, ensure_ascii=False)
            )
            print(f"📡 실시간 알림 발송: {user_id}")
            
        except Exception as e:
            print(f"❌ 실시간 알림 발송 실패: {e}")

    async def subscribe_user_notifications(self, user_id: str):
        """사용자별 알림 구독"""
        if not self.redis:
            return None
            
        try:
            pubsub = self.redis.pubsub()
            channel = f"notifications:user:{user_id}"
            await pubsub.subscribe(channel)
            return pubsub
            
        except Exception as e:
            print(f"❌ 알림 구독 실패: {e}")
            return None

# 전역 인스턴스
redis_store = RedisNotificationStore()