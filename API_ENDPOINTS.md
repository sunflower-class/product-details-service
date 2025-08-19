# Product Details Service API 엔드포인트 가이드

## 기본 정보
- **Base URL**: `https://oauth.buildingbite.com`
- **Content-Type**: `application/json`
- **인증**: `X-User-Id` 헤더 필수 (일부 엔드포인트 제외)

---

## 1. 상품 상세페이지 생성 관련

### 1.1 HTML 생성 요청 (비동기)
**POST** `/api/generation/display-list`

상품 정보를 받아 Worker 서비스로 HTML 생성 작업을 비동기 요청합니다.

**Headers:**
```
X-User-Id: string (필수)
X-Session-Id: string (선택)
```

**Request Body:**
```json
{
  "product_data": "상품명\n상품 설명\n가격: 10,000원\n브랜드: 샘플브랜드",
  "product_image_url": "https://example.com/image.jpg",
  "features": ["고품질", "친환경", "내구성"],
  "target_customer": "20-30대 직장인",
  "tone": "professional"
}
```

**Response (202 Accepted):**
```json
{
  "status": "ACCEPTED",
  "data": {
    "html_list": []
  },
  "task_id": "task_12345_abcdef"
}
```

---

### 1.2 작업 상태 조회
**GET** `/api/generation/generation/status/{task_id}`

HTML 생성 작업의 현재 상태를 조회합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Response:**
```json
{
  "success": true,
  "task_id": "task_12345_abcdef",
  "status": "processing",
  "message": "HTML 생성 중...",
  "progress": 60
}
```

**Status 값:**
- `pending`: 대기 중
- `processing`: 처리 중
- `completed`: 완료
- `failed`: 실패

---

### 1.3 작업 결과 조회
**GET** `/api/generation/generation/result/{task_id}`

완료된 HTML 생성 작업의 결과를 조회합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Response (성공시):**
```json
{
  "success": true,
  "task_id": "task_12345_abcdef",
  "status": "completed",
  "result": {
    "product_details_id": 123,
    "product_id": 456,
    "html_list": [
      "<div>생성된 HTML 블록 1</div>",
      "<div>생성된 HTML 블록 2</div>"
    ],
    "image_count": 3,
    "images": [
      {
        "id": 1,
        "url": "https://s3.amazonaws.com/bucket/image1.jpg",
        "image_source": "ORIGINAL",
        "image_type": "product"
      }
    ]
  }
}
```

**Response (진행중/실패시):**
```json
{
  "success": false,
  "task_id": "task_12345_abcdef",
  "status": "processing",
  "message": "Task is processing"
}
```

---

## 2. ProductDetails 관리

### 2.1 상품 상세 정보 조회
**GET** `/api/generation/product-details/{product_details_id}`

특정 ProductDetails ID로 상품 상세 정보와 연관 이미지를 조회합니다.

**Headers:**
```
X-User-Id: string (선택, 없으면 공개 조회)
```

**Response:**
```json
{
  "id": 123,
  "product_id": 456,
  "user_id": "user123",
  "user_session": "session456",
  "original_product_info": "원본 상품 정보 텍스트",
  "generated_html": {
    "html_blocks": ["<div>HTML 블록</div>"],
    "image_count": 2,
    "generation_completed": true
  },
  "used_templates": [1, 2],
  "used_categories": [1, 3],
  "status": "completed",
  "thumbnail": "https://s3.amazonaws.com/bucket/thumb.jpg",
  "created_at": "2025-01-20T10:30:00Z",
  "updated_at": "2025-01-20T11:00:00Z",
  "product_images": [
    {
      "id": 1,
      "product_details_id": 123,
      "s3_url": "https://s3.amazonaws.com/bucket/image1.jpg",
      "temp_url": "https://temp.url/image1.jpg",
      "image_source": "ORIGINAL",
      "image_type": "product",
      "is_uploaded_to_s3": true,
      "created_at": "2025-01-20T10:30:00Z"
    }
  ]
}
```

---

### 2.2 사용자 상품 목록 조회
**GET** `/api/generation/product-details`

사용자의 ProductDetails 목록을 조회합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Query Parameters:**
- `status`: 상태 필터 (`draft`, `completed`, `failed`, `published`, `archived`)
- `limit`: 조회할 항목 수 (기본값: 20)
- `offset`: 건너뛸 항목 수 (기본값: 0)

**Response:**
```json
{
  "total": 45,
  "items": [
    {
      "id": 123,
      "product_id": 456,
      "user_id": "user123",
      "original_product_info": "상품 정보...",
      "status": "completed",
      "thumbnail": "https://s3.amazonaws.com/bucket/thumb.jpg",
      "created_at": "2025-01-20T10:30:00Z",
      "updated_at": "2025-01-20T11:00:00Z"
    }
  ],
  "limit": 20,
  "offset": 0
}
```

---

### 2.3 상품 상세 정보 수정
**PUT** `/api/generation/product-details/{product_details_id}`

ProductDetails 정보를 수정합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Request Body:**
```json
{
  "product_id": 789,
  "original_product_info": "수정된 상품 정보",
  "generated_html": {
    "html_blocks": ["<div>수정된 HTML</div>"]
  },
  "status": "published"
}
```

**Response:**
```json
{
  "success": true,
  "message": "상품 상세 정보가 업데이트되었습니다 (필드: status, original_product_info)",
  "data": {
    "id": 123,
    "status": "published",
    "updated_at": "2025-01-20T12:00:00Z"
  }
}
```

---

### 2.4 상품 상세 정보 삭제
**DELETE** `/api/generation/product-details/{product_details_id}`

ProductDetails와 연관된 이미지들을 모두 삭제합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Response:**
```json
{
  "success": true,
  "message": "상품 상세 정보가 삭제되었습니다 (연관 이미지 3개 포함)",
  "data": {
    "deleted_product_details_id": 123,
    "deleted_image_count": 3
  }
}
```

---

## 3. Product 관리 (내부 상품 데이터)

### 3.1 상품 생성
**POST** `/api/products/`

새로운 상품을 생성합니다.

**Headers:**
```
X-User-Id: string (필수)
X-User-Session: string (선택)
```

**Request Body:**
```json
{
  "name": "샘플 상품",
  "description": "상품 설명",
  "category": "전자기기",
  "brand": "샘플브랜드",
  "price": 10000,
  "currency": "KRW",
  "original_product_data": "원본 상품 데이터 텍스트",
  "main_image_url": "https://example.com/image.jpg",
  "features": ["고품질", "친환경"],
  "target_customer": "20-30대",
  "tone": "professional",
  "status": "active",
  "is_published": false
}
```

**Response:**
```json
{
  "id": 456,
  "name": "샘플 상품",
  "description": "상품 설명",
  "category": "전자기기",
  "brand": "샘플브랜드",
  "price": 10000,
  "currency": "KRW",
  "original_product_data": "원본 상품 데이터 텍스트",
  "main_image_url": "https://example.com/image.jpg",
  "features": ["고품질", "친환경"],
  "target_customer": "20-30대",
  "tone": "professional",
  "status": "active",
  "is_published": false,
  "view_count": 0,
  "user_id": "user123",
  "user_session": "session456",
  "created_at": "2025-01-20T10:30:00Z",
  "updated_at": "2025-01-20T10:30:00Z",
  "published_at": null
}
```

---

### 3.2 상품 목록 조회
**GET** `/api/products/`

상품 목록을 조회합니다.

**Headers:**
```
X-User-Id: string (선택, 없으면 모든 상품 조회)
```

**Query Parameters:**
- `status`: 상품 상태 필터
- `category`: 카테고리 필터
- `search`: 검색어 (상품명, 설명, 브랜드)
- `is_published`: 퍼블리시 상태 필터 (true/false)
- `skip`: 건너뛸 항목 수 (기본값: 0)
- `limit`: 조회할 항목 수 (기본값: 20, 최대: 100)

**Response:**
```json
[
  {
    "id": 456,
    "name": "샘플 상품",
    "description": "상품 설명",
    "category": "전자기기",
    "price": 10000,
    "currency": "KRW",
    "status": "active",
    "is_published": true,
    "view_count": 15,
    "user_id": "user123",
    "created_at": "2025-01-20T10:30:00Z",
    "updated_at": "2025-01-20T11:00:00Z",
    "published_at": "2025-01-20T11:00:00Z"
  }
]
```

---

### 3.3 특정 상품 조회
**GET** `/api/products/{product_id}`

특정 상품의 상세 정보를 조회하고 조회수를 증가시킵니다.

**Headers:**
```
X-User-Id: string (선택, 없으면 관리자 모드)
```

**Response:**
```json
{
  "id": 456,
  "name": "샘플 상품",
  "description": "상품 설명",
  "category": "전자기기",
  "brand": "샘플브랜드",
  "price": 10000,
  "currency": "KRW",
  "original_product_data": "원본 상품 데이터",
  "main_image_url": "https://example.com/image.jpg",
  "features": ["고품질", "친환경"],
  "target_customer": "20-30대",
  "tone": "professional",
  "status": "active",
  "is_published": true,
  "view_count": 16,
  "user_id": "user123",
  "user_session": "session456",
  "created_at": "2025-01-20T10:30:00Z",
  "updated_at": "2025-01-20T11:00:00Z",
  "published_at": "2025-01-20T11:00:00Z"
}
```

---

### 3.4 상품과 연관 상세페이지 함께 조회
**GET** `/api/products/{product_id}/with-details`

상품 정보와 연관된 상세페이지들을 함께 조회합니다.

**Headers:**
```
X-User-Id: string (선택, 없으면 관리자 모드)
```

**Response:**
```json
{
  "id": 456,
  "name": "샘플 상품",
  "description": "상품 설명",
  "category": "전자기기",
  "price": 10000,
  "status": "active",
  "is_published": true,
  "view_count": 17,
  "user_id": "user123",
  "created_at": "2025-01-20T10:30:00Z",
  "updated_at": "2025-01-20T11:00:00Z",
  "product_details": [
    {
      "id": 123,
      "product_id": 456,
      "user_id": "user123",
      "status": "completed",
      "thumbnail": "https://s3.amazonaws.com/bucket/thumb.jpg",
      "created_at": "2025-01-20T10:30:00Z"
    }
  ],
  "product_details_count": 1
}
```

---

### 3.5 상품 수정
**PUT** `/api/products/{product_id}`

상품 정보를 수정합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Request Body:**
```json
{
  "name": "수정된 상품명",
  "price": 15000,
  "status": "active",
  "is_published": true
}
```

**Response:**
```json
{
  "id": 456,
  "name": "수정된 상품명",
  "price": 15000,
  "status": "active",
  "is_published": true,
  "updated_at": "2025-01-20T12:00:00Z",
  "published_at": "2025-01-20T12:00:00Z"
}
```

---

### 3.6 상품 삭제
**DELETE** `/api/products/{product_id}`

상품을 삭제합니다. 연관된 상세페이지들도 CASCADE로 함께 삭제됩니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Response:**
```json
{
  "success": true,
  "message": "상품이 성공적으로 삭제되었습니다"
}
```

---

### 3.7 상품 퍼블리시 상태 변경
**PATCH** `/api/products/{product_id}/publish?is_published=true`

상품의 퍼블리시 상태를 변경합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Query Parameters:**
- `is_published`: 퍼블리시 상태 (true/false)

**Response:**
```json
{
  "success": true,
  "message": "상품이 퍼블리시되었습니다",
  "is_published": true,
  "published_at": "2025-01-20T12:00:00Z"
}
```

---

### 3.8 상품 통계 조회
**GET** `/api/products/stats`

상품 관련 통계를 조회합니다.

**Headers:**
```
X-User-Id: string (선택, 없으면 전체 통계)
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_products": 45,
    "published_products": 30,
    "draft_products": 15,
    "categories": {
      "전자기기": 12,
      "의류": 8,
      "생활용품": 25
    },
    "total_views": 1250,
    "average_price": 25000
  }
}
```

---

## 4. 이미지 관련

### 4.1 이미지 생성
**POST** `/api/generation/image`

프롬프트와 원본 이미지로 새로운 이미지를 생성합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Request Body:**
```json
{
  "prompt_data": "고품질 상품 사진, 전문 조명",
  "image_url": "https://example.com/original.jpg"
}
```

**Response:**
```json
{
  "status": "SUCCESS",
  "data": {
    "image_url": "https://generated-image-url.com/new-image.jpg"
  }
}
```

---

### 4.2 이미지 업로드
**POST** `/api/generation/upload-image?url=https://example.com/image.jpg`

외부 이미지 URL을 서버에 다운로드하여 저장합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Query Parameters:**
- `url`: 다운로드할 이미지 URL

**Response:**
```json
{
  "filepath": "static/images/downloaded_image_123.jpg",
  "saved_url": "https://oauth.buildingbite.com/static/images/downloaded_image_123.jpg"
}
```

---

## 5. 유틸리티

### 5.1 헬스체크
**GET** `/api/generation/actuator/health`

서비스 상태를 확인합니다.

**Response:**
```json
{
  "status": "OK",
  "detail": "Running in development mode"
}
```

---

### 5.2 테스트 알림
**POST** `/api/generation/test/notification`

알림 플로우 테스트를 위한 작업을 등록합니다.

**Headers:**
```
X-User-Id: string (필수)
```

**Response:**
```json
{
  "success": true,
  "message": "테스트 작업이 등록되었습니다. Worker 서비스에서 처리 후 알림을 발송합니다.",
  "task_id": "task_test_12345",
  "instructions": [
    "1. Worker 서비스에서 이 작업을 처리합니다",
    "2. 처리 완료 후 Event Hub로 알림 이벤트를 발송합니다",
    "3. 알림 서비스에서 이벤트를 수신하여 알림을 처리합니다"
  ]
}
```

---

## 에러 응답 형식

모든 에러는 다음 형식으로 반환됩니다:

**4xx/5xx 에러:**
```json
{
  "detail": "에러 메시지"
}
```

**일반적인 에러 코드:**
- `400`: 잘못된 요청 (유효하지 않은 데이터)
- `401`: 인증 실패 (X-User-Id 헤더 누락)
- `403`: 권한 없음 (다른 사용자의 데이터 접근 시도)
- `404`: 리소스 없음
- `500`: 서버 내부 오류

---

## 주요 특징

1. **비동기 처리**: HTML 생성은 비동기로 처리되며, task_id로 상태와 결과를 조회할 수 있습니다.
2. **사용자 권한**: X-User-Id 헤더를 통해 사용자별 데이터 접근을 제어합니다.
3. **CASCADE 삭제**: Product 삭제 시 연관된 ProductDetails와 이미지들이 자동 삭제됩니다.
4. **이미지 관리**: S3 업로드와 임시 URL을 모두 지원합니다.
5. **통계 제공**: 상품 관련 다양한 통계 정보를 제공합니다.
6. **검색/필터**: 상품명, 카테고리, 상태 등으로 검색 및 필터링이 가능합니다.