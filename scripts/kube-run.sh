#!/bin/bash

# 사용자명 인자 체크
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "❌ Docker Hub 사용자명과 서비스이름을 인자로 입력해주세요."
  echo "예시: bash ./scripts/kube-run.sh chldlsrb1000 python-service"
  exit 1
fi

DOCKER_HUB_ID="$1"
SERVICE_NAME="$2"

echo ""
echo "🚀 [$SERVICE_NAME] 빌드 및 컨테이너 실행 중..."

TAG="${DOCKER_HUB_ID}/${SERVICE_NAME}:latest"

# 도커 이미지 빌드
docker build -t "$TAG" . || { echo "❌ Docker 빌드 실패: $TAG"; exit 1; }

# Docker Hub에 푸시
docker push "$TAG" || { echo "❌ Docker 푸시 실패: $TAG"; exit 1; }

# 불필요한 이미지 및 컨테이너 정리
docker image prune -f

kubectl delete -f kubernetes/deploy.yml || { echo "❌ kubernetes 실행 취소 실패"; }
kubectl apply -f kubernetes/deploy.yml || { echo "❌ kubernetes 배포 실패"; }

echo ""
echo "✅ $SERVICE_NAME 서비스가 실행되었습니다."
