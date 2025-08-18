#!/usr/bin/env python3
"""
HTML Generation Worker Service
독립적인 Worker 서비스로 Redis 큐에서 작업을 처리
"""
import asyncio
import json
import redis
import redis.exceptions
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

# Azure Redis 연결 설정
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

print(f"🔧 환경변수 확인:")
print(f"   REDIS_HOST: {REDIS_HOST}")
print(f"   REDIS_PORT: {REDIS_PORT}")
print(f"   REDIS_SSL: {REDIS_SSL}")
print(f"   REDIS_PASSWORD exists: {bool(REDIS_PASSWORD)}")

# 작업 큐 설정
TASK_QUEUE = "html_generation_queue"
RESULT_PREFIX = "html_result:"
STATUS_PREFIX = "html_status:"

class HtmlGenerationWorker:
    """HTML 생성 작업을 처리하는 Worker"""
    
    def __init__(self):
        self.redis_client = None
        self.running = False
        
    def connect_redis(self):
        """Redis 연결 (Azure Redis Cache 지원, 연결 풀 사용)"""
        try:
            # Azure Redis Cache 연결 - URL 방식 사용 (더 안정적)
            if REDIS_SSL:
                redis_url = f'rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
            else:
                redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
            
            # Azure Redis 최적화 설정
            self.redis_client = redis.from_url(
                redis_url, 
                decode_responses=True, 
                ssl_cert_reqs=None,
                socket_connect_timeout=15,  # 연결 타임아웃
                socket_timeout=30,          # Azure 권장: 긴 작업 대응
                socket_keepalive=True,      # 연결 유지 활성화
                socket_keepalive_options={
                    1: 60,  # TCP_KEEPIDLE: 60초 후 keep-alive 시작
                    2: 30,  # TCP_KEEPINTVL: 30초 간격으로 probe
                    3: 3,   # TCP_KEEPCNT: 3번 실패하면 연결 종료
                },
                health_check_interval=60,   # Azure Redis 10분 idle timeout 대응
                retry_on_timeout=True,      # 타임아웃 시 재시도
                retry_on_error=[            # 특정 에러 시 재시도
                    redis.exceptions.ConnectionError,
                    redis.exceptions.TimeoutError,
                    redis.exceptions.BusyLoadingError,
                ],
                max_connections=5,          # 연결 풀 크기 (Worker는 적게)
                connection_pool_kwargs={    # 추가 연결 풀 설정
                    'retry_on_timeout': True,
                    'socket_keepalive': True,
                }
            )
            
            # 연결 테스트
            self.redis_client.ping()
            print(f"✅ Redis 연결 성공: {REDIS_HOST}:{REDIS_PORT} (SSL: {REDIS_SSL})")
            return True
            
        except Exception as e:
            print(f"❌ Redis 연결 실패: {e}")
            self.redis_client = None
            return False
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """개별 작업 처리"""
        from src.services.html_generation_flow import html_flow
        
        task_id = task_data.get('task_id')
        
        try:
            print(f"🔄 작업 처리 시작: {task_id}")
            print(f"   사용자: {task_data.get('user_id')}")
            print(f"   제출 시간: {task_data.get('submitted_at')}")
            
            # 상태를 processing으로 업데이트
            self.update_task_status(task_id, 'processing')
            
            # HTML 생성 플로우 실행 (모든 작업 포함)
            # - Product 서비스 호출
            # - 이미지 생성 (Together AI, 추가 정보 반영)
            # - S3 업로드
            # - HTML 템플릿 생성 (특징, 타겟 고객, 톤 반영)
            # - DB 저장
            result = await html_flow.generate_complete_html(
                product_data=task_data['product_data'],
                product_image_url=task_data['product_image_url'],
                user_id=task_data['user_id'],
                user_session=task_data.get('user_session'),
                task_data=task_data,  # task_id 포함한 전체 데이터 전달
                features=task_data.get('features'),
                target_customer=task_data.get('target_customer'),
                tone=task_data.get('tone')
            )
            
            # 결과 저장
            if result['success']:
                self.update_task_status(task_id, 'completed')
                self.store_result(task_id, result)
                print(f"✅ 작업 완료: {task_id}")
                print(f"   ProductDetails ID: {result.get('product_details_id')}")
                print(f"   이미지 수: {result.get('image_count')}")
            else:
                self.update_task_status(task_id, 'failed', result.get('error'))
                self.store_result(task_id, result)
                print(f"❌ 작업 실패: {task_id} - {result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = f"Worker 처리 실패: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())
            
            self.update_task_status(task_id, 'failed', error_msg)
            
            error_result = {
                'success': False,
                'error': error_msg,
                'task_id': task_id
            }
            self.store_result(task_id, error_result)
            
            return error_result
    
    def update_task_status(self, task_id: str, status: str, error: Optional[str] = None):
        """작업 상태 업데이트 - Redis 연결 실패 시에도 계속 진행"""
        try:
            # 연결 상태 확인 및 재연결
            if not self._ensure_redis_connection():
                print(f"⚠️ Redis 연결 실패로 상태 업데이트 건너뛰기: {task_id} -> {status}")
                return
                
            status_key = f"{STATUS_PREFIX}{task_id}"
            status_data = {
                'status': status,
                'updated_at': datetime.now().isoformat()
            }
            
            if error:
                status_data['error'] = error
            
            # 상태 저장 (24시간 TTL)
            self.redis_client.setex(
                status_key,
                86400,
                json.dumps(status_data)
            )
            print(f"📝 상태 업데이트 성공: {task_id} -> {status}")
            
        except Exception as e:
            print(f"⚠️ Redis 상태 업데이트 실패 (무시하고 계속): {e}")
        
    def store_result(self, task_id: str, result: Dict[str, Any]):
        """작업 결과 저장 - Redis 연결 실패 시에도 계속 진행"""
        try:
            # 연결 상태 확인 및 재연결
            if not self._ensure_redis_connection():
                print(f"⚠️ Redis 연결 실패로 결과 저장 건너뛰기: {task_id}")
                return
                
            result_key = f"{RESULT_PREFIX}{task_id}"
            
            # 결과 저장 (24시간 TTL)
            self.redis_client.setex(
                result_key,
                86400,
                json.dumps(result)
            )
            print(f"💾 결과 저장 성공: {task_id}")
            
        except Exception as e:
            print(f"⚠️ Redis 결과 저장 실패 (무시하고 계속): {e}")
    
    async def run(self):
        """Worker 메인 루프 (Redis 연결 복원력 개선)"""
        if not self.connect_redis():
            print("Redis 연결 실패로 Worker를 시작할 수 없습니다.")
            return
        
        self.running = True
        print("=" * 60)
        print("🚀 HTML Generation Worker 시작")
        print(f"📌 큐 이름: {TASK_QUEUE}")
        print(f"🔧 환경: {os.environ.get('MODE', 'development')}")
        print("=" * 60)
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Redis 연결 상태 확인 및 재연결
                if not self._ensure_redis_connection():
                    print("⚠️ Redis 재연결 실패, 5초 후 재시도")
                    await asyncio.sleep(5)
                    continue
                
                # Redis 큐에서 작업 가져오기 (블로킹, 5초 타임아웃)
                task = self.redis_client.blpop(TASK_QUEUE, timeout=5)
                
                if task:
                    _, task_json = task
                    task_data = json.loads(task_json)
                    
                    print(f"\n📥 새 작업 수신: {task_data.get('task_id')}")
                    
                    # 비동기 작업 처리
                    await self.process_task(task_data)
                    
                    # 성공적으로 처리했으므로 에러 카운터 리셋
                    consecutive_errors = 0
                    
            except KeyboardInterrupt:
                print("\n⚠️ Worker 종료 신호 감지")
                self.running = False
                
            except redis.exceptions.ConnectionError as e:
                consecutive_errors += 1
                print(f"🔌 Redis 연결 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"❌ Redis 연결 오류가 {max_consecutive_errors}회 연속 발생. Worker 종료.")
                    self.running = False
                    break
                
                # Redis 연결 재시도
                print("🔄 Redis 재연결 시도...")
                await asyncio.sleep(min(consecutive_errors * 2, 30))  # 점진적 백오프 (최대 30초)
                self.redis_client = None  # 연결 객체 초기화
                
            except Exception as e:
                consecutive_errors += 1
                print(f"❌ Worker 루프 오류 ({consecutive_errors}/{max_consecutive_errors}): {e}")
                print(traceback.format_exc())
                
                if consecutive_errors >= max_consecutive_errors:
                    print(f"❌ 연속 오류가 {max_consecutive_errors}회 발생. Worker 종료.")
                    self.running = False
                    break
                
                await asyncio.sleep(min(consecutive_errors * 2, 30))  # 점진적 백오프
        
        print("👋 Worker 종료")
    
    def _ensure_redis_connection(self) -> bool:
        """Redis 연결 상태 확인 및 재연결"""
        try:
            if self.redis_client is None:
                return self.connect_redis()
                
            # 연결 상태 확인
            self.redis_client.ping()
            return True
            
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError, Exception):
            print("🔄 Redis 연결이 끊어짐, 재연결 시도...")
            self.redis_client = None
            return self.connect_redis()
    
    def stop(self):
        """Worker 중지"""
        self.running = False

async def main():
    """Worker 메인 함수"""
    worker = HtmlGenerationWorker()
    
    try:
        await worker.run()
    except KeyboardInterrupt:
        print("\n종료 중...")
        worker.stop()

if __name__ == "__main__":
    print("HTML Generation Worker Service v1.0")
    asyncio.run(main())