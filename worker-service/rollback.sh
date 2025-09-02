#!/bin/bash

# HTML Generation Worker 롤백 스크립트
# 이전 버전으로 즉시 롤백

set -e

echo "🔄 HTML Generation Worker 롤백 시작..."

# 1. 현재 상태 확인
echo "📋 현재 배포 상태:"
kubectl get pods -n sangsangplus-backend -l app=html-generation-worker

# 2. 이전 버전으로 롤백
echo "⏪ 이전 버전으로 롤백..."
kubectl set image deployment/html-generation-worker -n sangsangplus-backend worker=buildingbite/html-generation-worker:backup-20250902-004024

# 3. 롤아웃 상태 확인
echo "⏳ 롤백 진행 상태 확인..."
kubectl rollout status deployment/html-generation-worker -n sangsangplus-backend --timeout=300s

# 4. 롤백 완료 확인
echo "✅ 롤백 완료 상태 확인..."
kubectl get pods -n sangsangplus-backend -l app=html-generation-worker

echo ""
echo "✅ 롤백 완료!"
echo "📊 확인:"
echo "   - Pod 상태: kubectl get pods -n sangsangplus-backend -l app=html-generation-worker"
echo "   - 로그 확인: kubectl logs -n sangsangplus-backend -l app=html-generation-worker -f"