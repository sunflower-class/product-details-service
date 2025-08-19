# Notification Service 환경 설정 가이드

## 환경 변수 설정

notification-service가 정상적으로 작동하기 위한 환경 변수들입니다.

## 현재 설정된 환경 변수

현재 k8s-deployment.yaml에서 다음 환경 변수들이 설정되어 있습니다:

#### Redis 설정:
- `REDIS_HOST`: worker-service-secret에서 참조
- `REDIS_PORT`: 6380
- `REDIS_PASSWORD`: worker-service-secret에서 참조
- `REDIS_SSL`: worker-service-secret에서 참조

#### Event Hub 설정:
- `EVENTHUB_CONSUMER_CONNECTION_STRING`: notification Event Hub 연결 문자열
- `NOTIFICATION_EVENTHUB_NAME`: "notification"
- `EVENTHUB_CONSUMER_GROUP`: "$Default"

#### 알림 발송 설정 (개발팀용, 선택사항):
- `SLACK_WEBHOOK_URL`: Slack 알림용 (에러 알림 등)
- `DISCORD_WEBHOOK_URL`: Discord 알림용

## 문제 해결

### "❌ 알림 저장 실패: value is not an integer or out of range" 에러

이 에러는 Redis `setex` 명령에서 TTL 값이 정수가 아닐 때 발생합니다.

**해결됨:** 코드에서 `timedelta().total_seconds()` 값을 `int()`로 변환하도록 수정했습니다.

## 테스트 방법

### 1. 알림 시스템 테스트
```bash
# product-details-service에서 테스트 알림 발송
curl -X POST "https://api.buildingbite.com/product-details/api/generation/test/notification" \
  -H "X-User-Id: test-user-123"
```

### 2. Redis 연결 테스트
```bash
# notification-service 로그 확인
kubectl logs -f deployment/notification-service --namespace=sangsangplus-backend
```

### 3. Event Hub 연결 테스트
- worker-service에서 HTML 생성 완료 시 notification-service 로그 확인
- "📥 알림 수신" 메시지가 출력되는지 확인

## 프론트엔드 통합

프론트엔드에서 실시간 알림을 받으려면:

1. **SSE(Server-Sent Events) 연결**
   ```javascript
   const eventSource = new EventSource('/api/notifications/stream/USER_ID');
   eventSource.onmessage = function(event) {
     const notification = JSON.parse(event.data);
     // 알림 처리 로직
   };
   ```

2. **알림 목록 조회**
   ```javascript
   fetch('/api/notifications/USER_ID')
     .then(response => response.json())
     .then(data => {
       // 알림 목록 표시
     });
   ```

