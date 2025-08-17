#!/usr/bin/env python3
"""
Notification Service
Azure Event Hubs에서 알림 이벤트를 수신하여 실제 알림 발송 + FastAPI 서버
"""
import asyncio
import signal
import sys
import os
import uvicorn
from threading import Thread

from src.services.event_hub_consumer import EventHubConsumer
from src.api.notification_api import app

class NotificationService:
    """알림 서비스 메인 클래스"""
    
    def __init__(self):
        self.consumer = EventHubConsumer()
        self.running = False
        self.api_server = None
    
    async def start(self):
        """서비스 시작 - EventHub Consumer + FastAPI 서버"""
        self.running = True
        print(f"🔔 Notification Service 시작 ({os.environ.get('MODE', 'development')})")
        
        try:
            # FastAPI 서버를 별도 태스크로 시작
            api_task = asyncio.create_task(self._start_api_server())
            
            # EventHub Consumer를 별도 태스크로 시작
            consumer_task = asyncio.create_task(self.consumer.start_consuming())
            
            # 두 태스크 모두 실행
            await asyncio.gather(api_task, consumer_task)
            
        except KeyboardInterrupt:
            print("\\n⚠️ 서비스 중지")
            await self.stop()
        except Exception as e:
            print(f"❌ 서비스 실패: {e}")
            await self.stop()
    
    async def _start_api_server(self):
        """FastAPI 서버 시작"""
        config = uvicorn.Config(
            app, 
            host="0.0.0.0", 
            port=8080,
            log_level="info"
        )
        server = uvicorn.Server(config)
        print("🌐 FastAPI 서버 시작: http://0.0.0.0:8080")
        await server.serve()
    
    async def stop(self):
        """서비스 중지"""
        if self.running:
            self.running = False
            try:
                await self.consumer.stop()
                print("👋 Notification Service 중지")
            except Exception as e:
                print(f"⚠️ 서비스 중지 오류: {e}")

async def main():
    """메인 함수"""
    service = NotificationService()
    
    # 시그널 핸들러 설정
    def signal_handler():
        print("\\n종료 신호 수신...")
        asyncio.create_task(service.stop())
    
    # SIGINT, SIGTERM 핸들러 등록
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        print("\\n키보드 인터럽트로 종료")
    finally:
        await service.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n프로그램 종료")
        sys.exit(0)