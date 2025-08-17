#!/usr/bin/env python3
"""
HTML Generation Worker Service
독립적인 Worker 서비스로 Redis 큐에서 작업을 처리
"""
import asyncio
import json
import redis
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
        """Redis 연결 (Azure Redis Cache 지원)"""
        try:
            # Azure Redis Cache 연결 - URL 방식 사용 (더 안정적)
            if REDIS_SSL:
                redis_url = f'rediss://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
            else:
                redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
            
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
        except Exception as e:
            print(f"⚠️ Redis 상태 업데이트 실패 (무시하고 계속): {e}")
        
    def store_result(self, task_id: str, result: Dict[str, Any]):
        """작업 결과 저장 - Redis 연결 실패 시에도 계속 진행"""
        try:
            result_key = f"{RESULT_PREFIX}{task_id}"
            
            # 결과 저장 (24시간 TTL)
            self.redis_client.setex(
                result_key,
                86400,
                json.dumps(result)
            )
        except Exception as e:
            print(f"⚠️ Redis 결과 저장 실패 (무시하고 계속): {e}")
    
    async def run(self):
        """Worker 메인 루프"""
        if not self.connect_redis():
            print("Redis 연결 실패로 Worker를 시작할 수 없습니다.")
            return
        
        self.running = True
        print("=" * 60)
        print("🚀 HTML Generation Worker 시작")
        print(f"📌 큐 이름: {TASK_QUEUE}")
        print(f"🔧 환경: {os.environ.get('MODE', 'development')}")
        print("=" * 60)
        
        while self.running:
            try:
                # Redis 큐에서 작업 가져오기 (블로킹, 5초 타임아웃)
                task = self.redis_client.blpop(TASK_QUEUE, timeout=5)
                
                if task:
                    _, task_json = task
                    task_data = json.loads(task_json)
                    
                    print(f"\n📥 새 작업 수신: {task_data.get('task_id')}")
                    
                    # 비동기 작업 처리
                    await self.process_task(task_data)
                    
            except KeyboardInterrupt:
                print("\n⚠️ Worker 종료 신호 감지")
                self.running = False
                
            except Exception as e:
                print(f"❌ Worker 루프 오류: {e}")
                print(traceback.format_exc())
                await asyncio.sleep(5)  # 오류 발생 시 잠시 대기
        
        print("👋 Worker 종료")
    
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