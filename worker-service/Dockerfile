# HTML Generation Worker Service
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY src/ ./src/
COPY main.py .

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV MODE=kubernetes

# 헬스체크 제거 (Worker는 Redis 연결 상태를 자체적으로 관리)

# Worker 실행
CMD ["python", "main.py"]