# Notification Service 연동 가이드

## 개요
다른 서비스에서 Notification Service를 통해 사용자에게 알림을 발송하는 방법에 대한 가이드입니다.

## 알림 발송 방법

### 1. Azure Event Hub를 통한 알림 발송 (권장)

Event Hub로 알림 이벤트를 발송하면 Notification Service가 자동으로 처리합니다.

#### Python 예시 (Worker Service 방식)

```python
import os
import json
from azure.eventhub import EventHubProducerClient, EventData
from typing import Optional
from datetime import datetime

class NotificationClient:
    def __init__(self):
        self.connection_string = os.environ.get(
            "EVENTHUB_CONNECTION_STRING",
            "Endpoint=sb://sangsangplus-eventhubs.servicebus.windows.net/;SharedAccessKeyName=NotificationProducerKey;SharedAccessKey=9r2Q4Mx7bpO1IQJcZHrCz9R9e3m7Wq5Yq+AEhMONSSM=;EntityPath=notification"
        )
        self.event_hub_name = "notification"
        self.producer = None
        self._init_producer()
    
    def _init_producer(self):
        try:
            self.producer = EventHubProducerClient.from_connection_string(
                conn_str=self.connection_string
            )
            print(f"✅ EventHub Producer 연결: {self.event_hub_name}")
        except Exception as e:
            print(f"❌ EventHub Producer 실패: {e}")
    
    def send_notification(self, notification_data: dict) -> bool:
        """알림 이벤트 발송"""
        if not self.producer:
            return False
        
        try:
            event_data = EventData(
                body=json.dumps(notification_data, ensure_ascii=False, default=str)
            )
            
            event_data_batch = self.producer.create_batch(
                partition_key=notification_data.get('user_id')
            )
            event_data_batch.add(event_data)
            self.producer.send_batch(event_data_batch)
            
            print(f"📤 알림 발송: {notification_data.get('event_id')}")
            return True
            
        except Exception as e:
            print(f"❌ 알림 발송 실패: {e}")
            return False

# 사용 예시
client = NotificationClient()

# 성공 알림
success_notification = {
    "event_id": "order_success_12345",
    "service_type": "order-service",
    "message_type": "success",
    "user_id": "user123",
    "user_session": "session456",
    "title": "주문 완료",
    "message": "주문이 성공적으로 완료되었습니다.",
    "action_url": "/orders/12345",
    "action_label": "주문 보기",
    "data_url": "https://api.buildingbite.com/orders/api/orders/12345",
    "data_id": "12345",
    "metadata": {
        "order_id": "12345",
        "amount": 25000
    },
    "created_at": datetime.now().isoformat()
}

client.send_notification(success_notification)
```

#### Node.js 예시

```javascript
const { EventHubProducerClient } = require("@azure/event-hubs");

class NotificationClient {
    constructor() {
        this.connectionString = process.env.EVENTHUB_CONNECTION_STRING || 
            "Endpoint=sb://sangsangplus-eventhubs.servicebus.windows.net/;SharedAccessKeyName=NotificationProducerKey;SharedAccessKey=9r2Q4Mx7bpO1IQJcZHrCz9R9e3m7Wq5Yq+AEhMONSSM=;EntityPath=notification";
        this.eventHubName = "notification";
        this.producer = new EventHubProducerClient(this.connectionString);
    }

    async sendNotification(notificationData) {
        try {
            const eventDataBatch = await this.producer.createBatch({
                partitionKey: notificationData.user_id
            });

            eventDataBatch.tryAdd({
                body: JSON.stringify(notificationData)
            });

            await this.producer.sendBatch(eventDataBatch);
            console.log(`📤 알림 발송: ${notificationData.event_id}`);
            return true;

        } catch (error) {
            console.error("❌ 알림 발송 실패:", error);
            return false;
        }
    }

    async close() {
        await this.producer.close();
    }
}

// 사용 예시
const client = new NotificationClient();

const errorNotification = {
    event_id: "payment_error_67890",
    service_type: "payment-service",
    message_type: "error",
    user_id: "user123",
    title: "결제 실패",
    message: "결제 처리 중 오류가 발생했습니다.",
    action_url: "/payment/retry",
    action_label: "재시도",
    data_url: "https://api.buildingbite.com/payment/api/transactions/67890",
    data_id: "67890",
    metadata: {
        transaction_id: "67890",
        error_code: "CARD_DECLINED"
    },
    created_at: new Date().toISOString()
};

await client.sendNotification(errorNotification);
await client.close();
```

### 2. 직접 REST API 호출 (대안)

Notification Service의 내부 API를 직접 호출하는 방법입니다.

```python
import requests
import json

# Kubernetes 클러스터 내부에서 호출
NOTIFICATION_SERVICE_URL = "http://notification-service.sangsangplus-backend.svc.cluster.local"

def send_direct_notification(notification_data: dict):
    """Notification Service에 직접 알림 전송"""
    try:
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/internal/notifications",
            json=notification_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 알림 발송 성공")
            return True
        else:
            print(f"❌ 알림 발송 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 알림 발송 오류: {e}")
        return False
```

## 알림 이벤트 스키마

### 필수 필드

```json
{
  "event_id": "string",           // 고유 이벤트 ID
  "service_type": "string",       // 서비스 타입 (예: "order-service")
  "message_type": "string",       // success, error, warning, info, progress
  "user_id": "string",           // 알림 수신 사용자 ID
  "title": "string",             // 알림 제목
  "message": "string",           // 알림 메시지
  "created_at": "ISO_STRING"     // 생성 시간
}
```

### 선택 필드

```json
{
  "user_session": "string",       // 사용자 세션 ID
  "action_url": "string",         // 클릭 시 이동할 URL
  "action_label": "string",       // 액션 버튼 라벨
  "data_url": "string",          // 관련 데이터 API URL
  "data_id": "string",           // 관련 데이터 ID
  "metadata": {}                 // 추가 메타데이터
}
```

## 서비스별 연동 예시

### Order Service 연동

```python
class OrderNotificationService:
    def __init__(self):
        self.notification_client = NotificationClient()
    
    def notify_order_created(self, order_id: str, user_id: str):
        notification = {
            "event_id": f"order_created_{order_id}",
            "service_type": "order-service",
            "message_type": "info",
            "user_id": user_id,
            "title": "주문 접수 완료",
            "message": "주문이 접수되었습니다. 준비 중입니다.",
            "action_url": f"/orders/{order_id}",
            "action_label": "주문 상세",
            "data_url": f"https://api.buildingbite.com/orders/api/orders/{order_id}",
            "data_id": order_id,
            "metadata": {"order_id": order_id},
            "created_at": datetime.now().isoformat()
        }
        return self.notification_client.send_notification(notification)
    
    def notify_order_completed(self, order_id: str, user_id: str, total_amount: int):
        notification = {
            "event_id": f"order_completed_{order_id}",
            "service_type": "order-service",
            "message_type": "success",
            "user_id": user_id,
            "title": "주문 완료",
            "message": f"주문이 완료되었습니다. 총 {total_amount:,}원",
            "action_url": f"/orders/{order_id}/receipt",
            "action_label": "영수증 보기",
            "data_url": f"https://api.buildingbite.com/orders/api/orders/{order_id}",
            "data_id": order_id,
            "metadata": {
                "order_id": order_id,
                "total_amount": total_amount
            },
            "created_at": datetime.now().isoformat()
        }
        return self.notification_client.send_notification(notification)
```

### Payment Service 연동

```python
class PaymentNotificationService:
    def __init__(self):
        self.notification_client = NotificationClient()
    
    def notify_payment_failed(self, transaction_id: str, user_id: str, error_reason: str):
        notification = {
            "event_id": f"payment_failed_{transaction_id}",
            "service_type": "payment-service",
            "message_type": "error",
            "user_id": user_id,
            "title": "결제 실패",
            "message": f"결제가 실패했습니다: {error_reason}",
            "action_url": "/payment/retry",
            "action_label": "재시도",
            "data_url": f"https://api.buildingbite.com/payment/api/transactions/{transaction_id}",
            "data_id": transaction_id,
            "metadata": {
                "transaction_id": transaction_id,
                "error_reason": error_reason
            },
            "created_at": datetime.now().isoformat()
        }
        return self.notification_client.send_notification(notification)
```

### User Service 연동

```python
class UserNotificationService:
    def __init__(self):
        self.notification_client = NotificationClient()
    
    def notify_profile_updated(self, user_id: str):
        notification = {
            "event_id": f"profile_updated_{user_id}_{int(time.time())}",
            "service_type": "user-service",
            "message_type": "success",
            "user_id": user_id,
            "title": "프로필 업데이트",
            "message": "프로필이 성공적으로 업데이트되었습니다.",
            "action_url": "/profile",
            "action_label": "프로필 보기",
            "data_url": f"https://api.buildingbite.com/users/api/users/{user_id}",
            "data_id": user_id,
            "created_at": datetime.now().isoformat()
        }
        return self.notification_client.send_notification(notification)
    
    def notify_password_changed(self, user_id: str):
        notification = {
            "event_id": f"password_changed_{user_id}_{int(time.time())}",
            "service_type": "user-service",
            "message_type": "warning",
            "user_id": user_id,
            "title": "비밀번호 변경",
            "message": "비밀번호가 변경되었습니다. 본인이 아니라면 즉시 문의해주세요.",
            "action_url": "/security",
            "action_label": "보안 설정",
            "metadata": {"security_alert": True},
            "created_at": datetime.now().isoformat()
        }
        return self.notification_client.send_notification(notification)
```

## 환경 변수 설정

각 서비스에서 알림을 발송하려면 다음 환경 변수가 필요합니다:

### Kubernetes Deployment에 추가

```yaml
env:
# Azure Event Hub 설정
- name: EVENTHUB_CONNECTION_STRING
  value: "Endpoint=sb://sangsangplus-eventhubs.servicebus.windows.net/;SharedAccessKeyName=NotificationProducerKey;SharedAccessKey=9r2Q4Mx7bpO1IQJcZHrCz9R9e3m7Wq5Yq+AEhMONSSM=;EntityPath=notification"
- name: NOTIFICATION_EVENTHUB_NAME
  value: "notification"

# 서비스별 외부 URL (data_url에 사용)
- name: SERVICE_EXTERNAL_URL
  value: "https://api.buildingbite.com/your-service"
```

## 모니터링 및 디버깅

### 로그 확인

```bash
# Notification Service 로그
kubectl logs -f deployment/notification-service -n sangsangplus-backend

# 특정 사용자의 알림 확인
kubectl exec -it deployment/notification-service -n sangsangplus-backend -- \
  python -c "
from src.core.redis_client import redis_store
import asyncio
result = asyncio.run(redis_store.get_user_notifications('user123'))
print(result)
"
```

### 헬스체크

```bash
# Notification Service 상태 확인
curl http://notification-service.sangsangplus-backend.svc.cluster.local/health

# 외부에서 접근 (Ingress 설정 후)
curl https://api.buildingbite.com/notifications/health
```

## 베스트 프랙티스

### 1. 이벤트 ID 규칙
```
{service_type}_{action}_{resource_id}_{timestamp}
예: order_completed_12345_1699123456
```

### 2. 메시지 타입 사용 가이드
- **success**: 작업 완료, 성공적인 액션
- **error**: 오류, 실패한 작업
- **warning**: 주의 필요한 상황
- **info**: 일반 정보, 상태 변경
- **progress**: 진행 상황 업데이트

### 3. URL 설정
- **action_url**: 프론트엔드 페이지 경로 (상대 경로)
- **data_url**: API 엔드포인트 전체 URL (절대 경로)

### 4. 에러 처리
```python
try:
    result = notification_client.send_notification(notification)
    if not result:
        # 로깅 및 재시도 로직
        logger.warning(f"알림 발송 실패: {notification['event_id']}")
except Exception as e:
    # 알림 실패가 메인 로직에 영향주지 않도록
    logger.error(f"알림 발송 오류: {e}")
```

### 5. 중복 방지
같은 이벤트에 대해 중복 알림을 방지하려면 고유한 `event_id`를 사용하세요.

## 패키지 의존성

### Python
```txt
azure-eventhub>=5.11.0
requests>=2.31.0
```

### Node.js
```json
{
  "dependencies": {
    "@azure/event-hubs": "^5.11.0",
    "axios": "^1.6.0"
  }
}
```

## 문제 해결

### 일반적인 문제들

1. **Event Hub 연결 실패**
   - 연결 문자열 확인
   - 네트워크 정책 확인 (Istio 설정)

2. **알림이 전송되지 않음**
   - Event Hub 로그 확인
   - Notification Service 로그 확인
   - Redis 연결 상태 확인

3. **data_url 접근 불가**
   - 외부 URL 설정 확인
   - CORS 설정 확인
   - 인증 헤더 포함 여부 확인