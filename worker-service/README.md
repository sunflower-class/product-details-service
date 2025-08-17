# HTML Generation Worker Service

독립적인 Worker 서비스로 HTML 생성 작업을 백그라운드에서 처리합니다.

## 아키텍처

```
[Product Details API] 
    ↓ (작업 제출)
[Azure Redis Cache Queue]
    ↓ (작업 가져오기)
[Worker Pods (별도 노드 풀)]
    ↓ (처리)
    ├── Product Service 호출
    ├── Together AI로 이미지 생성
    ├── AWS S3에 이미지 업로드
    ├── HTML 템플릿 생성
    └── PostgreSQL에 결과 저장
```

## 주요 기능

- Redis 큐에서 작업을 가져와 처리
- Product Service와 연동하여 상품 정보 생성
- Together AI API를 사용한 이미지 생성
- AWS S3에 이미지 업로드
- HTML 템플릿 생성 및 DB 저장
- 작업 상태 추적 및 결과 저장

## 배포 방법

### 1. Docker 이미지 빌드

```bash
# Docker 이미지 빌드
docker build -t html-generation-worker:latest .

# 이미지 태깅
docker tag html-generation-worker:latest YOUR_REGISTRY/html-generation-worker:latest

# 레지스트리에 푸시
docker push YOUR_REGISTRY/html-generation-worker:latest
```

### 2. Kubernetes Secret 생성

```bash
# Namespace 생성
kubectl create namespace product-details

# Redis Secret 생성
kubectl create secret generic redis-secret \
  --from-literal=host="your-redis.redis.cache.windows.net" \
  --from-literal=password="your-redis-password" \
  -n product-details

# AWS Credentials Secret 생성
kubectl create secret generic aws-credentials \
  --from-literal=access-key-id="your-access-key" \
  --from-literal=secret-access-key="your-secret-key" \
  -n product-details

# AI Service Credentials Secret 생성
kubectl create secret generic ai-credentials \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=together-api-key="your-together-key" \
  -n product-details

# Database Secret 생성
kubectl create secret generic db-credentials \
  --from-literal=connection-string="postgresql://user:pass@host:5432/dbname" \
  -n product-details
```

### 3. Worker 노드 풀 설정

```bash
# AKS에서 Worker 전용 노드 풀 생성
az aks nodepool add \
  --resource-group myResourceGroup \
  --cluster-name myAKSCluster \
  --name workerpool \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --labels workload=worker node-pool=worker-pool \
  --node-taints worker-only=true:NoSchedule
```

### 4. 배포

```bash
# k8s-deployment.yaml 파일 수정 (이미지 주소, S3 버킷 이름 등)
vi k8s-deployment.yaml

# 배포
kubectl apply -f k8s-deployment.yaml
```

## 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| REDIS_HOST | Redis 호스트 | your-redis.redis.cache.windows.net |
| REDIS_PORT | Redis 포트 | 6380 |
| REDIS_PASSWORD | Redis 비밀번호 | - |
| REDIS_SSL | SSL 사용 여부 | true |
| AWS_ACCESS_KEY_ID | AWS Access Key | - |
| AWS_SECRET_ACCESS_KEY | AWS Secret Key | - |
| S3_BUCKET_NAME | S3 버킷 이름 | product-images-bucket |
| OPENAI_API_KEY | OpenAI API 키 | sk-... |
| TOGETHER_API_KEY | Together AI API 키 | - |
| PRODUCT_SERVICE_URL | Product 서비스 URL | http://product-service:8000 |
| DATABASE_URL | PostgreSQL 연결 문자열 | postgresql://... |

## 모니터링

```bash
# Worker Pod 상태 확인
kubectl get pods -n product-details -l app=html-generation-worker

# Worker 로그 확인
kubectl logs -f -n product-details -l app=html-generation-worker

# HPA 상태 확인
kubectl get hpa -n product-details

# Worker Pod이 실행 중인 노드 확인
kubectl get pods -n product-details -l app=html-generation-worker -o wide
```

## 스케일링

```bash
# 수동 스케일링
kubectl scale deployment html-generation-worker --replicas=5 -n product-details

# HPA 설정 변경
kubectl edit hpa html-generation-worker-hpa -n product-details
```

## 트러블슈팅

### Redis 연결 실패
- Azure Redis Cache 방화벽 규칙 확인
- SSL 설정 확인 (포트 6380 사용)
- 네트워크 정책 확인

### 이미지 생성 실패
- Together AI API 키 확인
- API 할당량 확인
- 네트워크 연결 확인

### S3 업로드 실패
- AWS 자격 증명 확인
- S3 버킷 권한 확인
- 버킷 정책 확인

### Worker가 특정 노드에서 실행되지 않음
- 노드 라벨 확인: `kubectl get nodes --show-labels`
- Taint/Toleration 설정 확인
- 노드 풀 상태 확인