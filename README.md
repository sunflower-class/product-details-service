# Product Details Service

상품 상세 페이지 HTML을 자동 생성하는 AI 기반 마이크로서비스입니다.

## 🚀 주요 기능

- **상품 정보 파싱**: 텍스트 입력을 구조화된 상품 데이터로 변환
- **AI 이미지 생성**: Together AI를 사용한 상품 이미지 자동 생성 
- **HTML 템플릿 시스템**: PostgreSQL 기반 템플릿 관리
- **S3 이미지 저장**: AWS S3 연동으로 이미지 영구 저장
- **Product 서비스 연동**: 상품 데이터 중앙 관리
- **Kafka 메시징**: 비동기 작업 처리

## 🏗️ 아키텍처

```
사용자 요청 → Product 생성 → 이미지 생성 → S3 업로드 → HTML 생성 → 결과 반환
              ↓                ↓              ↓           ↓
         Product Service   Together AI      AWS S3    PostgreSQL
```

## 📋 필요 환경

- **Python**: v3.10.12
- **PostgreSQL**: 상품 상세 데이터 저장
- **Product Service**: 상품 정보 관리
- **Together AI**: 이미지 생성
- **OpenAI GPT-4**: HTML 컨텐츠 생성
- **AWS S3**: 이미지 저장 (선택)

## ⚙️ 환경 설정

### 필수 환경변수

```bash
# 데이터베이스
DATABASE_URL=postgresql://user:password@host:5432/product_details_db

# 외부 서비스
PRODUCT_SERVICE_URL=http://product-service
OPENAI_API_KEY=sk-...
TOGETHER_API_KEY=tgp_v1_...

# S3 설정 (선택)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=your-bucket
AWS_REGION=ap-northeast-2
```

### Kubernetes Secret 설정

```bash
kubectl apply -f kubernetes/secret.yaml
```

## 🛠️ 설치 및 실행

### 로컬 개발환경

```bash
# 가상환경 설정
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements-minimal.txt

# 서버 실행
uvicorn src.main:app --host 0.0.0.0 --port 5001 --reload
```

### Docker 실행

```bash
bash ./scripts/docker-run.sh <DOCKER_HUB_ID> <SERVICE_NAME> <SERVICE_PORT>
```

### Kubernetes 배포

```bash
# Azure 로그인 및 클러스터 연결
az login --use-device-code
az aks get-credentials --resource-group <RESOURCE_GROUP> --name <CLUSTER_NAME>

# 배포 실행
bash scripts/kube-run.sh <DOCKER_HUB_ID>
```

## 📊 데이터베이스 스키마

### 주요 테이블

- **`product_details`**: 생성된 HTML 상세 페이지
- **`product_images`**: 원본/생성된 이미지 관리
- **`templates`**: HTML 템플릿 저장
- **`categories`**: 템플릿 카테고리

### 초기 데이터베이스 설정

```sql
-- database/init.sql 실행
psql -h hostname -U username -d database -f database/init.sql
```

## 🔌 API 엔드포인트

### 인증
모든 주요 엔드포인트에서 `X-User-Id` 헤더 필수

### 주요 API

| 엔드포인트 | 메서드 | 설명 | 인증 |
|-----------|--------|------|------|
| `/api/generation/actuator/health` | GET | 헬스 체크 | ❌ |
| `/api/generation/display-list` | POST | **전체 HTML 생성 플로우** | ✅ |
| `/api/generation/image` | POST | 이미지 수정/생성 | ✅ |
| `/api/generation/upload-image` | POST | 이미지 업로드 | ✅ |
| `/api/generation/message` | POST | Kafka 메시지 테스트 | ❌ |

### 핵심 API 사용법

#### HTML 생성 (전체 플로우)

```bash
curl -X POST "http://localhost:5001/api/generation/display-list" \
  -H "X-User-Id: user123" \
  -H "Content-Type: application/json" \
  -d '{
    "product_data": "아이폰 15 프로 최신형 스마트폰 가격 150만원 애플 브랜드",
    "product_image_url": "https://example.com/image.jpg"
  }'
```

**응답 예시:**
```json
{
  "status": "success",
  "data": {
    "html_list": ["<div>...</div>", "<div>...</div>"],
    "product_details_id": 123,
    "product_id": 456,
    "image_count": 4
  }
}
```

## 🔄 전체 처리 플로우

1. **요청 접수**: `product_data`와 `product_image_url` 수신
2. **텍스트 파싱**: 상품명, 가격, 브랜드 등 추출
3. **Product 생성**: Product 서비스에 구조화된 데이터 전송
4. **DB 레코드 생성**: `product_details` 테이블에 초기 레코드
5. **원본 이미지 저장**: 사용자 제공 이미지를 `ORIGINAL`로 저장
6. **AI 이미지 생성**: Together AI로 추가 이미지 3개 생성
7. **S3 업로드**: 이미지들을 S3에 업로드 (설정 시)
8. **HTML 생성**: 모든 이미지를 사용하여 HTML 블록 생성
9. **최종 저장**: 완성된 HTML을 DB에 저장
10. **결과 반환**: 생성된 HTML과 메타데이터 반환

## 🚨 에러 처리

- **Fail-Fast**: 각 단계에서 실패 시 즉시 중단
- **상태 관리**: 실패한 작업은 `status='failed'`로 기록
- **폴백 처리**: 실패 시 기본 HTML 템플릿 반환
- **로그 기록**: 모든 단계별 로그 출력

## 🧪 테스트

### 헬스 체크
```bash
curl http://localhost:5001/api/generation/actuator/health
```

### 전체 플로우 테스트
```bash
curl -X POST "http://localhost:5001/api/generation/display-list" \
  -H "X-User-Id: test-user" \
  -H "Content-Type: application/json" \
  -d '{
    "product_data": "테스트 상품입니다",
    "product_image_url": "https://via.placeholder.com/400"
  }'
```

## 📱 모니터링

### Kubernetes 명령어

```bash
# 서비스 상태 확인
kubectl get all

# 로그 확인
kubectl logs -f deployment/product-details-service

# 재시작
kubectl rollout restart deployment/product-details-service

# 서비스 제거
kubectl delete -f kubernetes/deploy.yml
```

### 데이터베이스 모니터링

```sql
-- 처리 현황 확인
SELECT status, COUNT(*) FROM product_details GROUP BY status;

-- 최근 생성된 항목
SELECT * FROM product_details ORDER BY created_at DESC LIMIT 10;

-- 이미지 통계
SELECT image_source, COUNT(*) FROM product_images GROUP BY image_source;
```

## 🔧 개발자 정보

### 주요 변경사항 (v2.0)

- ✅ ChromaDB 제거로 메모리 사용량 60% 감소
- ✅ PostgreSQL 기반 템플릿 시스템 도입
- ✅ Product 서비스 연동 추가
- ✅ AI 이미지 생성 및 S3 저장 자동화
- ✅ 전체 HTML 생성 플로우 구현
- ✅ X-User-Id 기반 인증 시스템

### 기술 스택

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Database**: PostgreSQL, Azure Database
- **AI Services**: OpenAI GPT-4o-mini, Together AI
- **Storage**: AWS S3
- **Messaging**: Kafka
- **Container**: Docker, Kubernetes
- **Cloud**: Azure AKS

