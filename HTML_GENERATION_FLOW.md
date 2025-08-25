# HTML 생성 플로우 문서

## 개요
product-details-service의 `/api/generation/display-list` 엔드포인트를 통한 HTML 생성 전체 플로우

## 전체 아키텍처
```
User Request → product-details-service → Redis Queue → worker-service → HTML Generation
```

## 상세 플로우

### 1. 요청 접수 (product-details-service)
- **엔드포인트**: `/api/generation/display-list`
- **파일**: `src/api/endpoints.py`
- **처리 과정**:
  1. Product 레코드 생성 (메인 서비스 DB)
  2. Redis 큐에 작업 제출 (`task_manager.submit_task()`)
  3. 202 응답 반환 (task_id 포함)

### 2. 작업 처리 (worker-service)
- **파일**: `worker-service/main.py`
- **처리 과정**:
  1. Redis 큐 모니터링
  2. `html_generation_flow.generate_complete_html()` 실행

### 3. HTML 생성 상세 프로세스

#### 3.1 ProductDetails 생성
- 메인 서비스에서 생성된 Product ID 사용
- 생성 설정을 metadata에 저장

#### 3.2 이미지 처리 (개선사항 적용)
**원본 이미지 처리**:
- URL이 있으면 저장, 없으면 AI 생성만 사용
- 플레이스홀더 URL인 경우 무시

**AI 이미지 생성**:
- 원본 이미지가 없으면 3개 생성 (기본 2개 + 1개 추가)
- 원본 이미지가 있으면 2개 추가 생성
- **S3 URL 우선 사용** (S3 업로드 실패 시 temp URL 사용)

#### 3.3 템플릿 추천
- **ChromaDB 유사도 검색**: 284개 템플릿 중에서 검색
- 상품 정보, 특징, 타겟 고객, 톤에 기반한 검색
- 거리 임계값 1.5 (관대한 설정)

#### 3.4 HTML 생성 방식 (2가지)

**A. 고급 방식** (`generate_advanced_html`) - 우선 시도
- ChromaDB 연결 시 사용
- 상품 분석 → 블록별 콘셉트 → 템플릿 매칭 → HTML 생성
- **개선사항**:
  - 추가 이미지 URL들을 갤러리로 포함
  - 템플릿 구조 보존하되 텍스트는 상품 정보로 교체

**B. 하이브리드 방식** (`generate_hybrid_html`) - 폴백
- ChromaDB 연결 실패 시 또는 고급 방식 실패 시 사용
- **개선사항**:
  - 템플릿의 디자인 스타일만 참고, 텍스트는 상품 정보로 교체
  - 추가 이미지 URL들을 HTML에 포함
  - "PREMIUM PRODUCT" 등 템플릿 텍스트 복사 금지

#### 3.5 결과 저장
- ProductDetails 테이블에 HTML 저장
- 첫 번째 S3 이미지를 썸네일로 설정
- Redis에 결과 저장 (24시간 TTL)
- 알림 서비스로 완료 통지

## 주요 개선사항

### 1. 원본 이미지 처리
- **기존**: 항상 원본 이미지 필수
- **개선**: URL이 없으면 AI 생성으로 대체, 이미지 개수 자동 조정

### 2. 템플릿 과도 반영 문제 해결
- **기존**: 템플릿 텍스트를 그대로 복사
- **개선**: 디자인 스타일만 참고, 상품 정보로 텍스트 교체

### 3. AI 생성 이미지 미사용 문제 해결
- **기존**: 생성된 이미지를 HTML에서 사용하지 않음
- **개선**: S3 URL을 우선 사용하여 HTML에 포함

### 4. ChromaDB 템플릿 업데이트
- 284개 템플릿으로 업데이트 완료
- 유사도 검색 정확도 향상

## 파일별 역할

### product-details-service
- `src/api/endpoints.py`: 요청 접수, Product 생성, Redis 작업 제출
- `src/services/task_manager.py`: Redis 큐 관리
- `src/services/product_service.py`: Product CRUD
- `src/services/create_image.py`: 이미지 생성 API 엔드포인트용

### worker-service
- `src/services/html_generation_flow.py`: 전체 HTML 생성 플로우 관리
- `src/services/create_html_advanced.py`: 고급 HTML 생성 (ChromaDB 기반)
- `src/services/create_html_hybrid.py`: 하이브리드 HTML 생성 (폴백용)
- `src/services/image_manager.py`: AI 이미지 생성 및 S3 업로드
- `src/services/template_recommendation_service.py`: ChromaDB 템플릿 추천

### notification-service
- 작업 완료 알림 처리

## 설정 환경변수
- `MAX_GENERATED_IMAGES`: AI 생성 이미지 개수 (기본값: 2)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`: Redis 연결 설정
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`: S3 업로드 설정
- `OPENAI_API_KEY`: GPT API 키
- `TOGETHER_API_KEY`: 이미지 생성 API 키

## 로그 메시지 의미
- "🎯 고급 HTML 생성 모드 사용": ChromaDB 연결되어 고급 방식 시도
- "⚠️ 고급 방식 실패, 기존 방식으로 폴백": 하이브리드 방식으로 전환
- "⚠️ ChromaDB 연결 불가, 기존 방식 사용": 처음부터 하이브리드 방식 사용
- "📸 S3 URL 사용": S3 업로드된 이미지 사용
- "📸 임시 URL 사용": S3 업로드 실패로 임시 URL 사용

## 문제 해결
1. **이미지가 HTML에 포함되지 않는 경우**: S3 업로드 설정 확인
2. **템플릿이 과도하게 반영되는 경우**: GPT 프롬프트 수정으로 해결됨
3. **ChromaDB 연결 실패**: 하이브리드 방식으로 자동 폴백