# kafka-python-server
kafka 연결을 위한 python 보일러 플레이트 저장소 입니다.

# Initialize Setting
- Python 버전: v3.10.12
- venv 사용
- fastapi 서버 사용

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# 사전 준비
- docker: v28.x ('25.7.7 기준 lts)
- docker compose: v2.x ('25.7.7 기준 lts)

# 사용법 (도커, 개발환경)

## 실행

```
bash ./scripts/docker-run.sh <DOCKER HUB ID> <SERVICE NAME> <SERVICE PORT: 옵션>
```
- 위 명령어 사용시 `docker 빌드 -> docker push -> docker run` 순서로 진행됩니다.
- `SERVICE PORT` 는 외부에서 접근 가능한 포트입니다.

```
uvicorn src.app:app --host 0.0.0.0 --port 5001 --reload
```
- 위 명령어 사용시 개발환경에서 동작합니다.

### 테스트

```
curl -X GET "http://localhost:5001/python"
```
- 초기 상태일 때 테스트 가능
- `python API is running!` 라는 메세지 수신 시 테스트 성공

## 서비스 변경

- `@app.route('/python/**')` 경로를 수정해주세요.
- 수정 후 `gateway` 저장소의 서비스도 수정해야합니다.

# 배포 (쿠버네티스)

## 사전 설정

### azure 설치

```
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### azure 로그인

```
az login --use-device-code
```

### 쿠버네티스 클러스터 연결

```
az aks get-credentials --resource-group <마이크로소프트 리소스 그룹> --name <마이크로소프트 쿠버네티스 클러스터>
```

### 쿠버네티스 CLI 도구 설치
- 링크 참조: https://kubernetes.io/ko/docs/tasks/tools/install-kubectl-linux/

## 쿠버네티스 설정 실행

```
bash scripts/kube-run.sh <DOCKER HUB ID>
```

- 각 설정에 따라 `kubernetes/deploy.yml` 을 수정해주세요.
- image 는 docker hub에 올린 이미지 사용 (기본: `chldlsrb1000/python-service:latest`)

### 추가 명령어

```
# 제거하기
kubectl delete -f kubernetes/deploy.yml

# 확인하기 (pods, services, deployments..)
kubectl get all

# 로그확인(-f: 실시간 옵션)
kubectl logs <POD NAME>

# 바로 재반영
kubectl get deployment  # 확인
kubectl rollout restart deployment/gateway  # 재반영
```
