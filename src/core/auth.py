"""
인증 및 사용자 검증 모듈
X-User-Id 헤더 검증 및 추출
"""
from fastapi import HTTPException, Header
from typing import Optional

def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """
    X-User-Id 헤더에서 사용자 ID를 추출하고 검증합니다.
    
    Args:
        x_user_id: X-User-Id 헤더 값
        
    Returns:
        검증된 사용자 ID
        
    Raises:
        HTTPException: X-User-Id 헤더가 없거나 유효하지 않은 경우
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="X-User-Id header is required",
            headers={"WWW-Authenticate": "X-User-Id"}
        )
    
    # 사용자 ID 형식 검증 (선택적)
    if len(x_user_id.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header cannot be empty"
        )
    
    # 추가 검증 로직 (필요 시)
    # - 길이 제한 (예: 100자 이하)
    # - 특수문자 제한
    # - 데이터베이스에서 사용자 존재 여부 확인 등
    
    user_id = x_user_id.strip()
    
    if len(user_id) > 100:
        raise HTTPException(
            status_code=400,
            detail="X-User-Id header is too long (max 100 characters)"
        )
    
    return user_id

def get_optional_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[str]:
    """
    선택적으로 X-User-Id 헤더를 추출합니다.
    헤더가 없어도 예외를 발생시키지 않습니다.
    
    Args:
        x_user_id: X-User-Id 헤더 값
        
    Returns:
        사용자 ID 또는 None
    """
    if not x_user_id or len(x_user_id.strip()) == 0:
        return None
    
    user_id = x_user_id.strip()
    
    if len(user_id) > 100:
        return None
    
    return user_id

# 미들웨어로 전역 적용할 수도 있음 (선택사항)
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

class UserIdMiddleware(BaseHTTPMiddleware):
    """
    모든 요청에 대해 X-User-Id 헤더를 검증하는 미들웨어
    """
    
    def __init__(self, app, excluded_paths: list = None):
        super().__init__(app)
        # X-User-Id가 필요하지 않은 경로들
        self.excluded_paths = excluded_paths or [
            "/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/generation/actuator/health"
        ]
    
    async def dispatch(self, request: Request, call_next):
        # 제외된 경로는 검증하지 않음
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # X-User-Id 헤더 검증
        user_id = request.headers.get("X-User-Id")
        
        if not user_id or len(user_id.strip()) == 0:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "X-User-Id header is required",
                    "error_code": "MISSING_USER_ID"
                },
                headers={"WWW-Authenticate": "X-User-Id"}
            )
        
        if len(user_id.strip()) > 100:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "X-User-Id header is too long (max 100 characters)",
                    "error_code": "INVALID_USER_ID"
                }
            )
        
        # 요청에 사용자 ID 추가 (선택사항)
        request.state.user_id = user_id.strip()
        
        return await call_next(request)