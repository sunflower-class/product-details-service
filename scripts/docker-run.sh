#!/bin/bash

# 공통 설정
NETWORK="kafka_docker_network" # 도커 네트워크 이름(kafka + docker compose 네트워크)

# 사용자명 인자 체크
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "❌ Docker Hub 사용자명과 서비스이름을 인자로 입력해주세요."
  echo "예시: bash ./scripts/docker-run.sh chldlsrb1000 python-service 8091"
  exit 1
fi

DOCKER_HUB_ID="$1"
SERVICE_NAME="$2"
PORT="$3"

# 포트 매핑 옵션을 담을 변수 초기화 (빈 문자열)
PORT_OPTS=""

# PORT 변수가 비어있지 않은 경우 (포트가 입력된 경우)
if [ -n "$PORT" ]; then
  # PORT_OPTS 변수에 포트 매핑 옵션 문자열을 할당
  PORT_OPTS="-p $PORT:5001"
fi

# 네트워크 생성
docker network create "$NETWORK" 2>/dev/null || echo "네트워크 '$NETWORK'이 이미 존재합니다."

echo ""
echo "🚀 [$SERVICE_NAME] 빌드 및 컨테이너 실행 중..."

TAG="${DOCKER_HUB_ID}/${SERVICE_NAME}:dev"

# 도커 이미지 빌드
docker build -t "$TAG" . || { echo "❌ Docker 빌드 실패: $TAG"; exit 1; }

# Docker Hub에 푸시
docker push "$TAG" || { echo "❌ Docker 푸시 실패: $TAG"; exit 1; }

# 기존 컨테이너 삭제
docker rm -f $SERVICE_NAME 2>/dev/null

# 도커 실행
docker run -d --name $SERVICE_NAME \
  $PORT_OPTS \
  --network "$NETWORK" \
  "$TAG"

# 불필요한 이미지 및 컨테이너 정리
docker image prune -f

echo ""
echo "✅ $SERVICE_NAME 서비스가 실행되었습니다."
