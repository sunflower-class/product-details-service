# Product Details Service - K8s 배포 위험성 분석 보고서

## 📋 서비스 개요

이 서비스는 AI 모델을 활용하여 상품 정보를 HTML 코드로 변환하고, 이미지를 생성/편집하는 기능을 제공합니다.

### 주요 엔드포인트 분석

#### 1. `GET /api/generation/` 
- **기능**: 서비스 상태 확인
- **리소스 영향**: 최소

#### 2. `POST /api/generation/message`
- **기능**: Kafka로 메시지 전송
- **리소스 영향**: 낮음 (현재 development 모드로 Kafka 비활성화)

#### 3. `GET /api/generation/actuator/health`
- **기능**: 헬스체크 엔드포인트
- **리소스 영향**: 최소

#### 4. `POST /api/generation/display-list` ⚠️
- **기능**: 상품 정보를 받아 HTML 코드 생성
- **처리 과정**:
  1. OpenAI GPT-4o-mini를 호출하여 페이지 구조 생성
  2. ChromaDB에서 템플릿 검색 (벡터 유사도 검색)
  3. 각 블록별로 GPT-4o-mini를 재호출하여 HTML 생성
  4. 이미지 프롬프트가 있을 경우 Together AI API 호출하여 이미지 생성
- **리소스 영향**: **매우 높음** (다중 LLM API 호출 + 벡터 DB 검색)

#### 5. `POST /api/generation/image` ⚠️
- **기능**: 이미지 URL을 받아 프롬프트대로 수정
- **처리 과정**:
  1. GPT-4o-mini로 프롬프트 번역 (한글→영어)
  2. Together AI의 FLUX.1-kontext-dev 모델로 이미지 생성
- **리소스 영향**: **높음** (2개의 AI 모델 순차 호출)

#### 6. `POST /api/generation/upload-image`
- **기능**: 이미지 다운로드 및 저장
- **리소스 영향**: 중간 (네트워크 I/O + 파일시스템 쓰기)

## 🚨 주요 우려사항

### 1. **CPU 스파이크 문제 (매우 심각)**

**현상**: 귀하가 우려한 대로, 이 서비스도 **CPU 점유율이 조울증처럼 오락가락할 가능성이 매우 높습니다.**

**원인**:
- **AI 모델이 외부 API가 아닌 로컬에서 실행**: 
  - ChromaDB 벡터 검색 (CPU 집약적)
  - sentence-transformers 임베딩 생성 (로컬 실행 시 CPU 사용)
  - PyTorch, transformers 라이브러리 포함 (모델 로딩 가능성)

- **동기적 처리 방식**:
  - 한 요청당 최대 5-10회의 LLM API 호출
  - 각 호출이 순차적으로 처리되어 응답 시간이 길어짐

### 2. **메모리 부족 위험 (심각)**

**현재 설정**:
```yaml
resources:
  requests:
    memory: "280Mi"
    cpu: "210m"
  limits:
    memory: "350Mi"  # 너무 낮음!
    cpu: "500m"
```

**문제점**:
- **ChromaDB 로딩**: 최소 100-200MB
- **ML 라이브러리 로딩**: 
  - PyTorch: 300-500MB
  - sentence-transformers: 200-300MB
  - 총합: 600MB-1GB 필요
- **결과**: **OOMKilled(Out of Memory) 발생 가능성 높음**

### 3. **콜드 스타트 문제**

- `initialDelaySeconds: 120` 설정에도 불구하고 모델 로딩 시간이 부족할 수 있음
- 특히 sentence-transformers 모델 초기 로딩 시 2-3분 소요 가능

### 4. **리소스 경쟁 문제**

- 단일 replica로 운영 중
- 동시 요청 시 CPU 경쟁으로 인한 성능 저하
- 한 요청이 CPU를 독점하면 다른 요청들이 타임아웃 될 수 있음

## 📊 예상 시나리오

### 요청 1개 처리 시:
1. 요청 수신
2. ChromaDB 벡터 검색 → **CPU 30-50% 스파이크 (1-2초)**
3. GPT-4o-mini API 호출 (3-5회) → CPU 정상
4. Together AI 이미지 생성 → CPU 정상
5. 응답 완료
6. **CPU 0-5%로 복귀**

### 동시 요청 3개 이상:
- **CPU 100% 도달**
- 메모리 부족으로 스왑 발생
- 응답 시간 10초 → 60초 이상으로 증가
- Liveness probe 실패 → **Pod 재시작 루프**

## 🔧 권장 사항

### 1. **즉시 조치 필요**
```yaml
resources:
  requests:
    memory: "1Gi"    # 최소 1GB
    cpu: "500m"       # 0.5 코어
  limits:
    memory: "2Gi"    # 최대 2GB
    cpu: "2000m"      # 2 코어
```

### 2. **아키텍처 개선 제안**

#### Option A: 모델 서빙 분리 (권장)
- ChromaDB를 별도 서비스로 분리
- 벡터 임베딩 생성을 별도 서비스로 분리
- 메인 서비스는 API 오케스트레이션만 담당

#### Option B: 비동기 처리
- Celery/Redis 도입하여 작업 큐 구성
- 장시간 작업을 백그라운드로 처리
- 사용자에게는 작업 ID 반환 후 폴링

### 3. **모니터링 설정**
- Prometheus로 CPU/Memory 메트릭 수집
- 95 percentile 응답 시간 모니터링
- OOM 발생 빈도 추적

### 4. **스케일링 전략**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: product-details-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: product-details-service
  minReplicas: 2
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60  # 60% 이상시 스케일링
```

## 🎯 결론

현재 구조로는 **프로덕션 환경에서 안정적인 운영이 불가능**합니다. 
특히 우려하신 대로 CPU 사용률이 급격히 변동하며, 메모리 부족으로 인한 서비스 중단이 빈번하게 발생할 것으로 예상됩니다.

**우선순위**:
1. 🔴 메모리 리소스 즉시 증설 (최소 1GB)
2. 🟠 ChromaDB/임베딩 모델 분리
3. 🟡 HPA 설정 및 replica 증가
4. 🟢 비동기 처리 도입 검토

---
*작성일: 2025-08-13*

## 🔍 서버-워커 분리 아키텍처 분석 보고서

### 현재 의존성 분석

#### 1. **ChromaDB 사용 현황**
- **사용 위치**: `src/services/create_html.py`의 26-40줄
- **초기화 시점**: 모듈 로드 시점에 즉시 실행
- **실제 사용**: `get_concept_html_template()` 함수에서 벡터 유사도 검색
- **리소스 부담**: 
  - ChromaDB 클라이언트 초기화
  - CSV 파일(data.csv) 로드 및 임베딩 생성
  - 매 요청마다 벡터 검색 수행

#### 2. **AI 모델 호출 패턴**
**외부 API 호출 (리소스 부담 낮음):**
- OpenAI GPT-4o-mini (LangChain 통해 호출)
- Together AI FLUX 모델 (이미지 생성)

**로컬 실행 가능성 있는 부분:**
- sentence-transformers (requirements.txt에 주석 처리됨)
- PyTorch, transformers (주석 처리됨)
- 현재는 주석 처리되어 있으나, ChromaDB가 내부적으로 임베딩 생성 시 사용할 가능성

### 서버-워커 분리 방안

#### **Option 1: Message Queue 기반 분리 (권장)**

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   FastAPI   │────▶│ Redis/RabbitMQ│────▶│   Worker     │
│   Server    │     │    Queue     │     │   Process    │
└─────────────┘     └──────────────┘     └──────────────┘
      │                                          │
      │                                          ├─▶ ChromaDB
      └─▶ 요청 ID 반환                           ├─▶ OpenAI API
                                                ├─▶ Together API
                                                └─▶ 결과 저장
```

**구현 방법:**
1. FastAPI 서버는 요청만 받고 큐에 작업 추가
2. 별도 워커 프로세스가 ChromaDB와 AI 호출 처리
3. Celery + Redis 또는 RQ(Redis Queue) 사용

**장점:**
- 서버 메모리 부담 완전 제거
- 워커 수평 확장 가능
- 장애 격리

**단점:**
- 구현 복잡도 증가
- 응답 시간 증가 (폴링 필요)

#### **Option 2: Microservice 분리**

```
┌─────────────┐     ┌──────────────┐
│   FastAPI   │────▶│  ChromaDB    │
│   Server    │ HTTP│  Service     │
└─────────────┘     └──────────────┘
      │                     
      ├─────────────────────▶ OpenAI API
      └─────────────────────▶ Together API
```

**구현 방법:**
1. ChromaDB를 별도 FastAPI 서비스로 분리
2. 메인 서버는 HTTP 호출로 벡터 검색 요청
3. AI API 호출은 메인 서버에서 직접 수행

**장점:**
- 구현이 상대적으로 단순
- ChromaDB만 격리 가능
- 동기적 처리로 응답 속도 유지

**단점:**
- 네트워크 오버헤드 추가
- 서비스 간 통신 관리 필요

#### **Option 3: 경량화 전략 (단기 해결책)**

**즉시 적용 가능한 개선사항:**

1. **ChromaDB Lazy Loading**
```python
# create_html.py 수정
_chroma_client = None
_collection = None

def get_chroma_collection():
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path="src/_data/chroma_db")
        _collection = _chroma_client.get_or_create_collection(name="html_template_search_engine")
        # CSV 로드 및 추가 로직
    return _collection
```

2. **ChromaDB 완전 제거 및 대체**
- 템플릿을 JSON/YAML 파일로 관리
- 간단한 키워드 매칭 또는 규칙 기반 선택
- Elasticsearch 같은 경량 검색 엔진 사용

3. **캐싱 전략**
- Redis로 ChromaDB 검색 결과 캐싱
- LRU 캐시로 자주 사용되는 템플릿 메모리 캐싱

### 의존성 제거 로드맵

#### Phase 1: ChromaDB 격리 (1-2주)
1. ChromaDB 관련 코드를 별도 모듈로 분리
2. 인터페이스 추상화 (Repository 패턴)
3. Mock 구현으로 개발 환경 테스트

#### Phase 2: 비동기 처리 도입 (2-3주)
1. Celery + Redis 설정
2. 작업 큐 구현
3. 폴링 또는 웹소켓으로 결과 전달

#### Phase 3: 완전 분리 (3-4주)
1. ChromaDB 서비스 컨테이너화
2. 워커 프로세스 컨테이너화
3. K8s에서 별도 Deployment로 관리

### 리소스 최적화 예상 효과

**현재 상태:**
- 메모리: 600MB-1GB (ChromaDB + ML 라이브러리)
- CPU: 스파이크 발생 (벡터 검색 시)

**분리 후 예상:**
- **API 서버**: 메모리 200-300MB, CPU 안정적
- **워커**: 메모리 500MB-1GB, CPU 집중 작업 격리
- **확장성**: 워커만 스케일 아웃 가능

### 권장 우선순위

1. 🔴 **즉시**: ChromaDB Lazy Loading 적용
2. 🟠 **1주 내**: Redis 캐싱 도입
3. 🟡 **2주 내**: Message Queue 기반 비동기 처리
4. 🟢 **1개월 내**: 완전한 마이크로서비스 분리

### 결론

ChromaDB가 실제로 프로젝트에서 제한적으로 사용되고 있음을 확인했습니다. 벡터 검색이 꼭 필요하지 않다면 **완전 제거**가 가장 효과적입니다. 만약 유지해야 한다면 **Message Queue 기반 워커 분리**가 리소스 부담을 크게 줄일 수 있는 최선의 방법입니다.

현재 모든 AI 모델 호출이 외부 API를 통해 이루어지므로, ChromaDB만 격리하면 서버의 메모리/CPU 부담을 크게 줄일 수 있습니다.

---
*추가 작성일: 2025-08-15*

## 🎯 ChromaDB 제거 및 PostgreSQL 마이그레이션 로드맵

### 현재 문제점
1. **ChromaDB 의존성이 리소스 과부하 유발**
   - 벡터 임베딩 생성/검색이 CPU 집약적
   - 앱 시작 시 메모리 600MB-1GB 사용
   
2. **UX 문제**
   - 시스템이 자동으로 템플릿 선택 → 사용자 선택권 없음
   - 벡터 유사도 기반 선택이 사용자 의도와 불일치 가능

3. **확장성 제한**
   - 새 템플릿 추가 시 임베딩 재생성 필요
   - 템플릿 관리가 코드 레벨에서만 가능

### 제안 아키텍처

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Frontend    │────▶│   FastAPI    │────▶│   Azure      │
│              │     │   Server     │     │  PostgreSQL  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │
       ▼                    ▼
   템플릿 선택          CRUD API
   UI 제공             제공

데이터 플로우:
1. 사용자가 프론트에서 카테고리/템플릿 선택
2. FastAPI가 PostgreSQL에서 템플릿 조회
3. 선택된 템플릿 + 상품 정보로 HTML 생성
```

### 데이터베이스 스키마 설계

```sql
-- 카테고리 테이블
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 템플릿 테이블
CREATE TABLE templates (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    name VARCHAR(200) NOT NULL,
    block_type VARCHAR(50) NOT NULL, -- 'Introduction', 'KeyFeatures', etc.
    template_html TEXT NOT NULL,
    thumbnail_url VARCHAR(500),
    usage_count INTEGER DEFAULT 0,
    metadata JSONB, -- 추가 설정, 스타일 정보 등
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 템플릿 그룹 (한 상품 페이지에 사용될 템플릿 세트)
CREATE TABLE template_sets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 템플릿 세트 매핑
CREATE TABLE template_set_items (
    id SERIAL PRIMARY KEY,
    set_id INTEGER REFERENCES template_sets(id),
    template_id INTEGER REFERENCES templates(id),
    display_order INTEGER NOT NULL,
    UNIQUE(set_id, template_id)
);

-- 인덱스
CREATE INDEX idx_templates_category ON templates(category_id);
CREATE INDEX idx_templates_block_type ON templates(block_type);
CREATE INDEX idx_template_sets_category ON template_sets(category_id);
```

### API 엔드포인트 설계

```python
# 템플릿 관리 API
GET    /api/templates                 # 템플릿 목록 조회 (필터링, 페이징)
GET    /api/templates/{id}            # 특정 템플릿 조회
POST   /api/templates                 # 템플릿 생성
PUT    /api/templates/{id}            # 템플릿 수정
DELETE /api/templates/{id}            # 템플릿 삭제

# 카테고리 관리 API
GET    /api/categories                # 카테고리 목록
GET    /api/categories/{id}/templates # 카테고리별 템플릿 목록

# 템플릿 세트 API
GET    /api/template-sets             # 템플릿 세트 목록
GET    /api/template-sets/{id}        # 템플릿 세트 상세
POST   /api/template-sets             # 템플릿 세트 생성
PUT    /api/template-sets/{id}        # 템플릿 세트 수정

# 상품 페이지 생성 API (수정)
POST   /api/generation/display-list   # template_set_id 또는 template_ids 받음
```

### 구현 단계별 로드맵

#### **Phase 1: 데이터베이스 준비 (Week 1)**

1. Azure PostgreSQL 데이터베이스 생성
2. 스키마 생성 및 마이그레이션 스크립트 작성
3. SQLAlchemy 모델 정의
4. 기존 CSV 데이터를 PostgreSQL로 마이그레이션

**작업 내용:**
```python
# models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Template(Base):
    __tablename__ = 'templates'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'))
    name = Column(String(200), nullable=False)
    block_type = Column(String(50), nullable=False)
    template_html = Column(Text, nullable=False)
    # ...
```

#### **Phase 2: API 개발 (Week 1-2)**

1. CRUD 엔드포인트 구현
2. 템플릿 조회 최적화 (캐싱, 인덱싱)
3. 페이지네이션 및 필터링 구현
4. API 문서화 (Swagger/OpenAPI)

**주요 변경사항:**
```python
# src/services/template_service.py
async def get_templates_by_category(category_id: int, db: Session):
    return db.query(Template).filter(
        Template.category_id == category_id
    ).all()

async def create_html_with_templates(
    product_info: str,
    template_ids: List[int],
    db: Session
):
    templates = db.query(Template).filter(
        Template.id.in_(template_ids)
    ).all()
    # HTML 생성 로직 (ChromaDB 제거)
```

#### **Phase 3: ChromaDB 제거 (Week 2)**

1. `create_html.py`에서 ChromaDB 관련 코드 제거
2. 벡터 검색 로직을 템플릿 ID 기반 조회로 변경
3. `requirements.txt`에서 불필요한 의존성 제거:
   - chromadb
   - sentence-transformers (주석 해제 후 제거)
   - 관련 ML 라이브러리들

**의존성 정리:**
```txt
# 제거할 패키지
- chromadb
- onnxruntime
- sentence-transformers
- torch
- transformers
- triton

# 추가할 패키지
+ psycopg2-binary
+ alembic (마이그레이션)
```

#### **Phase 4: 쿠팡 데이터 기반 템플릿 생성 (Week 2-3)**

1. **크롤링 데이터 전처리**
   - 카테고리별 100개 상세페이지 분석
   - HTML 구조 파싱 및 공통 패턴 추출

2. **군집 분석 파이프라인**
   ```python
   # 별도 분석 스크립트
   - HTML 구조 특징 추출
   - K-means/DBSCAN으로 유형 분류
   - 각 군집별 대표 템플릿 선정
   ```

3. **템플릿 자동 생성**
   - 군집별 대표 HTML을 템플릿화
   - 변수 치환 가능한 형태로 변환
   - PostgreSQL에 bulk insert

#### **Phase 5: 프론트엔드 통합 (Week 3-4)**

1. **템플릿 선택 UI 구현**
   - 카테고리별 템플릿 목록 표시
   - 템플릿 미리보기 기능
   - 드래그앤드롭으로 템플릿 순서 조정

2. **사용자 플로우 개선**
   ```
   1. 상품 정보 입력
   2. 카테고리 선택
   3. 템플릿 세트 선택 또는 개별 템플릿 선택
   4. 미리보기
   5. HTML 생성 및 다운로드
   ```

### 예상 효과

#### **리소스 개선**
- **Before**: 메모리 600MB-1GB, CPU 스파이크
- **After**: 메모리 200-300MB, CPU 안정적
- 앱 시작 시간 50% 단축

#### **성능 개선**
- 템플릿 조회: 벡터 검색 → DB 인덱스 조회 (10배 빠름)
- 동시 요청 처리 능력 3배 향상

#### **UX 개선**
- 사용자가 원하는 템플릿 직접 선택 가능
- 템플릿 미리보기로 결과 예측 가능
- 템플릿 커스터마이징 가능

#### **관리 편의성**
- 웹 인터페이스로 템플릿 관리
- A/B 테스트 가능 (usage_count 트래킹)
- 버전 관리 및 롤백 가능

### 리스크 및 대응 방안

1. **데이터 마이그레이션 실패**
   - 백업 후 진행
   - 단계별 검증
   - 롤백 계획 수립

2. **API 하위 호환성**
   - 기존 API 유지하며 새 API 추가
   - Deprecation 기간 설정
   - 버전닝 (/v1, /v2)

3. **템플릿 품질 저하**
   - 초기에는 수동 검수
   - 사용자 피드백 시스템 구축
   - 템플릿 평가 메트릭 도입

### 타임라인

```
Week 1: DB 설계 및 마이그레이션
Week 2: API 개발 및 ChromaDB 제거
Week 3: 쿠팡 데이터 분석 및 템플릿 생성
Week 4: 프론트엔드 통합 및 테스트
Week 5: 배포 및 모니터링
```

### 결론

ChromaDB를 PostgreSQL로 대체하면:
1. **리소스 사용량 70% 감소**
2. **사용자 경험 대폭 개선**
3. **확장성 및 관리 편의성 향상**

특히 쿠팡 크롤링 데이터 기반 템플릿 자동 생성으로 고품질 템플릿을 대량 확보할 수 있으며, 사용자가 직접 템플릿을 선택할 수 있게 되어 만족도가 크게 향상될 것으로 예상됩니다.

---
*추가 작성일: 2025-08-15*