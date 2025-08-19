"""
Task Manager for async task submission to Redis queue
"""
import json
import uuid
import redis
import os
from typing import Dict, Any, Optional
from datetime import datetime

from src.core.config import settings

class TaskManager:
    """Redis 큐를 통한 비동기 작업 관리"""
    
    def __init__(self):
        self.redis_client = None
        self.task_queue = "html_generation_queue"
        self.status_prefix = "html_status:"
        self.result_prefix = "html_result:"
        
    def connect(self) -> bool:
        """Redis 연결 (Azure Redis Cache 지원)"""
        try:
            # 환경변수 읽기
            REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
            REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
            REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
            REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"
            
            # Redis URL 방식으로 연결 (SSL 인증서 검증 비활성화)
            if REDIS_SSL:
                redis_url = f"rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
            else:
                redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
            
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True,
                ssl_cert_reqs=None,
                socket_connect_timeout=10,
                socket_timeout=10
            )
            self.redis_client.ping()
            print(f"✅ Redis 연결 성공: {REDIS_HOST}:{REDIS_PORT}")
            return True
            
        except Exception as e:
            print(f"❌ Redis 연결 실패: {e}")
            return False
    
    def submit_task(
        self,
        product_data: str,
        product_image_url: str,
        user_id: str,
        product_id: int,  # Product ID 추가
        user_session: Optional[str] = None,
        features: Optional[list] = None,
        target_customer: Optional[str] = None,
        tone: Optional[str] = None
    ) -> Dict[str, Any]:
        """작업을 Redis 큐에 제출"""
        
        if not self.redis_client:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Redis connection failed'
                }
        
        # 고유한 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # 작업 데이터 준비
        task_data = {
            'task_id': task_id,
            'product_id': product_id,  # Product ID 추가
            'product_data': product_data,
            'product_image_url': product_image_url,
            'user_id': user_id,
            'user_session': user_session,
            'features': features,
            'target_customer': target_customer,
            'tone': tone,
            'submitted_at': datetime.now().isoformat()
        }
        
        try:
            # 초기 상태 설정
            status_key = f"{self.status_prefix}{task_id}"
            initial_status = {
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            }
            
            # 상태 저장 (24시간 TTL)
            self.redis_client.setex(
                status_key,
                86400,
                json.dumps(initial_status)
            )
            
            # 큐에 작업 추가
            self.redis_client.rpush(
                self.task_queue,
                json.dumps(task_data)
            )
            
            print(f"📋 작업 제출 완료: {task_id}")
            
            return {
                'success': True,
                'task_id': task_id,
                'message': 'HTML generation task submitted successfully'
            }
            
        except Exception as e:
            print(f"❌ 작업 제출 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """작업 상태 조회"""
        
        if not self.redis_client:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Redis connection failed'
                }
        
        try:
            status_key = f"{self.status_prefix}{task_id}"
            status_json = self.redis_client.get(status_key)
            
            if not status_json:
                return {
                    'success': False,
                    'error': 'Task not found'
                }
            
            status_data = json.loads(status_json)
            
            return {
                'success': True,
                'task_id': task_id,
                'status': status_data.get('status'),
                'created_at': status_data.get('created_at'),
                'updated_at': status_data.get('updated_at'),
                'error': status_data.get('error')
            }
            
        except Exception as e:
            print(f"❌ 상태 조회 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """작업 결과 조회"""
        
        if not self.redis_client:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Redis connection failed'
                }
        
        try:
            # 먼저 상태 확인
            status = self.get_task_status(task_id)
            
            if not status['success']:
                return status
            
            # 완료되지 않은 경우
            if status['status'] != 'completed':
                return {
                    'success': False,
                    'task_id': task_id,
                    'status': status['status'],
                    'message': f"Task is {status['status']}"
                }
            
            # 결과 조회
            result_key = f"{self.result_prefix}{task_id}"
            result_json = self.redis_client.get(result_key)
            
            if not result_json:
                return {
                    'success': False,
                    'error': 'Result not found'
                }
            
            result_data = json.loads(result_json)
            
            return {
                'success': True,
                'task_id': task_id,
                'result': result_data
            }
            
        except Exception as e:
            print(f"❌ 결과 조회 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# 전역 인스턴스
task_manager = TaskManager()