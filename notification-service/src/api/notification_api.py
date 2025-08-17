"""
Notification REST API
"""
import asyncio
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import time

from src.core.redis_client import redis_store


app = FastAPI(
    title="Notification Service API",
    description="실시간 알림 서비스",
    version="1.0.0"
)

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포시에는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSE 연결 관리 (사용자별)
active_connections: Dict[str, List] = {}


@app.get("/api/notifications/{user_id}")
async def get_user_notifications(
    user_id: str = Path(..., description="사용자 ID"),
    limit: int = Query(20, ge=1, le=100, description="조회할 알림 수"),
    offset: int = Query(0, ge=0, description="시작 위치")
):
    """사용자의 알림 목록 조회"""
    try:
        notifications = await redis_store.get_user_notifications(user_id, limit, offset)
        unread_count = await redis_store.get_unread_count(user_id)
        
        return {
            "success": True,
            "data": {
                "notifications": notifications,
                "unread_count": unread_count,
                "total_returned": len(notifications),
                "limit": limit,
                "offset": offset
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"알림 조회 실패: {e}")


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str = Path(..., description="알림 ID"),
    user_id: str = Query(..., description="사용자 ID")
):
    """알림을 읽음으로 표시"""
    try:
        success = await redis_store.mark_notification_read(notification_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없거나 권한이 없습니다")
        
        return {
            "success": True,
            "message": "알림이 읽음으로 처리되었습니다"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"읽음 처리 실패: {e}")


@app.delete("/api/notifications/{notification_id}")
async def delete_notification(
    notification_id: str = Path(..., description="알림 ID"),
    user_id: str = Query(..., description="사용자 ID")
):
    """알림 삭제"""
    try:
        success = await redis_store.delete_notification(notification_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없거나 권한이 없습니다")
        
        return {
            "success": True,
            "message": "알림이 삭제되었습니다"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {e}")


@app.get("/api/notifications/{user_id}/unread-count")
async def get_unread_count(
    user_id: str = Path(..., description="사용자 ID")
):
    """사용자의 읽지 않은 알림 개수"""
    try:
        unread_count = await redis_store.get_unread_count(user_id)
        
        return {
            "success": True,
            "data": {
                "unread_count": unread_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"개수 조회 실패: {e}")


@app.get("/api/notifications/stream/{user_id}")
async def stream_notifications(
    user_id: str = Path(..., description="사용자 ID")
):
    """Server-Sent Events 스트림"""
    
    async def event_stream():
        # 연결 등록
        if user_id not in active_connections:
            active_connections[user_id] = []
        
        connection_id = f"{user_id}_{int(time.time())}"
        active_connections[user_id].append(connection_id)
        
        pubsub = None
        try:
            # Redis pub/sub 구독 시작
            pubsub = await redis_store.subscribe_user_notifications(user_id)
            if not pubsub:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Redis 연결 실패'})}\n\n"
                return
            
            # 연결 확인 메시지
            yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id, 'timestamp': time.time()})}\n\n"
            
            # 30초마다 keepalive 전송
            last_keepalive = time.time()
            
            while True:
                try:
                    # Redis에서 메시지 확인 (non-blocking)
                    message = await asyncio.wait_for(pubsub.get_message(), timeout=2.0)
                    
                    if message and message['type'] == 'message':
                        # 실시간 알림 데이터 전송
                        notification_data = json.loads(message['data'])
                        yield f"data: {json.dumps({'type': 'notification', 'data': notification_data})}\n\n"
                    
                except asyncio.TimeoutError:
                    # 타임아웃 시 keepalive 체크
                    current_time = time.time()
                    if current_time - last_keepalive > 30:
                        yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': current_time})}\n\n"
                        last_keepalive = current_time
                        
                except Exception as e:
                    print(f"❌ Redis 메시지 처리 오류: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break
                
        except Exception as e:
            print(f"❌ SSE 스트림 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # 연결 해제
            if pubsub:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                except:
                    pass
            
            if user_id in active_connections and connection_id in active_connections[user_id]:
                active_connections[user_id].remove(connection_id)
                if not active_connections[user_id]:
                    del active_connections[user_id]
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


async def broadcast_notification_to_user(user_id: str, notification_data: Dict[str, Any]):
    """특정 사용자의 모든 SSE 연결에 알림 브로드캐스트"""
    if user_id in active_connections:
        # 실제 구현에서는 각 연결에 알림을 전송
        # 현재는 로그만 출력
        print(f"📡 SSE 브로드캐스트: {user_id} ({len(active_connections[user_id])} 연결)")


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {"status": "healthy", "service": "notification-api"}


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Notification Service API",
        "version": "1.0.0",
        "endpoints": {
            "notifications": "/api/notifications/{user_id}",
            "sse_stream": "/api/notifications/stream/{user_id}",
            "health": "/health"
        }
    }