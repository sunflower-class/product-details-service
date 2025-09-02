#!/bin/bash

# HTML Generation Worker - 동시 처리 버전 배포 스크립트
# 백업 이미지: buildingbite/html-generation-worker:backup-20250902-004024

set -e

echo "🚀 HTML Generation Worker 동시 처리 버전 배포 시작..."

# 1. 현재 상태 확인
echo "📋 현재 배포 상태 확인..."
kubectl get pods -n sangsangplus-backend -l app=html-generation-worker

# 2. 새 배포 적용
echo "⚡ 새 배포 적용 (동시 처리 지원)..."
kubectl apply -f k8s-deployment.yaml
kubectl apply -f k8s-pdb.yaml
kubectl apply -f k8s-hpa.yaml

# 3. 롤아웃 상태 확인
echo "⏳ 롤아웃 진행 상태 확인..."
kubectl rollout status deployment/html-generation-worker -n sangsangplus-backend --timeout=300s

# 4. 새 Pod 상태 확인
echo "✅ 새 Pod 상태 확인..."
kubectl get pods -n sangsangplus-backend -l app=html-generation-worker

# 5. 로그 확인 (동시 처리 기능 확인)
echo "📄 새 Pod 로그 확인 (최근 30줄)..."
NEW_POD=$(kubectl get pods -n sangsangplus-backend -l app=html-generation-worker --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}')
if [ -n "$NEW_POD" ]; then
    echo "📄 Pod: $NEW_POD"
    kubectl logs -n sangsangplus-backend $NEW_POD --tail=30
else
    echo "⚠️ 새 Pod를 찾을 수 없습니다."
fi

echo ""
echo "🎯 배포 완료!"
echo "📊 모니터링:"
echo "   - Pod 상태: kubectl get pods -n sangsangplus-backend -l app=html-generation-worker"
echo "   - HPA 상태: kubectl get hpa -n sangsangplus-backend html-generation-worker-hpa"
echo "   - 로그 확인: kubectl logs -n sangsangplus-backend -l app=html-generation-worker -f"
echo ""
echo "🔄 롤백 방법 (문제 발생 시):"
echo "   kubectl set image deployment/html-generation-worker -n sangsangplus-backend worker=buildingbite/html-generation-worker:backup-20250902-004024"
echo "   kubectl rollout undo deployment/html-generation-worker -n sangsangplus-backend"