# ☁️ cloud-monitor

쿠버네티스를 활용한 클라우드 리소스 모니터링 시스템  
Kubernetes 클러스터의 리소스를 DaemonSet으로 수집하고, 시계열 기반으로 저장/조회할 수 있는 모니터링 서비스입니다.

---

## 📌 1. 프로젝트 개요

![architecture](https://github.com/user-attachments/assets/3ecfeead-9ac4-47ad-a1a6-6c1ee65b1ed8)

### 🛰️ Agent (DaemonSet)
- 각 노드에 배포되어 10초마다 리소스 및 메타데이터 수집
- 수집 항목: `CPU`, `Memory`, `Disk IO`, `Network`, `Pod`, `Namespace`, `Deployment`
- 수집 방식: `/proc`, `/sys/fs/cgroup` 파싱
- JSON 형태로 중앙 API 서버에 전송

### 🌐 중앙 API 서버 (Flask)
- 수집 데이터를 시계열(JSON 파일)로 저장  
  (`nodes.json`, `pods.json`, `namespaces.json`, `deployments.json`)
- 10초 단위 타임윈도우 버킷 구조로 저장
- 제공 API 예시:
  - `POST /api/ingest`
  - `GET /api/nodes`, `/api/pods`, `/api/namespaces`, `/api/deployments`
  - `GET /api/nodes/<node>`, `/api/nodes/<node>/pods`
  - 모든 API에서 시계열 조회 가능

---

## 📁 2. 디렉토리 구조

![structure](https://github.com/user-attachments/assets/717e146e-7b89-4b7c-8551-78d160bfc54a)

---

## ⚙️ 3. 주요 기능 설명

### 📍 agent/metadata_collector.py
- pause PID → Pod UID → Pod ID → Container ID → 메타데이터 추출
- 각 pod의 메타데이터 수집:
  - `pod_name`, `namespace`, `deployment`, `pod_uid`, `container_id`, `PID`, `cgroup_path`

### 📍 agent/resource_collector.py
- 리소스 수집 항목:
  - **CPU**: `/sys/fs/cgroup/.../cpu.stat`
  - **Memory**: `/memory.current`
  - **Disk IO**: `/io.stat` → `disk_read_bytes`, `disk_write_bytes`
  - **Network**: `/proc/[pid]/net/dev` → `network_rx_bytes`, `network_tx_bytes`

### 📍 agent/main.py
- 10초마다 주기적으로 실행
- 단위별 리소스 집계 및 전송:
  - Pod → Namespace → Deployment → Node
- `collect_node_data()` → `send_to_server()`

### 📍 central_api_server/main.py
- 수신한 데이터를 시계열 버킷으로 저장
  - `__all__` 키로 전체 클러스터 정보도 저장
- 저장 파일:
  - `nodes.json`, `pods.json`, `namespaces.json`, `deployments.json`
- 타임윈도우 집계:
  - 10초 단위로 정규화하여 누적 저장

### 📍 monitor.yaml
- 에이전트 DaemonSet 정의 (모든 노드에 배포)

### 📍 monitor-api.yaml
- 중앙 API 서버의 Deployment + Service 정의

---

## 🧪 4. 개발환경 구축 및 배포

### 📌 4.1 개발환경
- `kubectl`만 설치되어 있어도 OK

### 📌 4.2 빌드 & 배포

```bash
chmod +x deploy
./deploy

### 📌 4.3 이미지 수동 배포 (Worker Node용)

```bash
# 워커 노드로 이미지 전송 및 가져오기 (한 번에 실행 가능)
scp monitor.tar monitor-api.tar ubuntu@<worker-node>:/tmp/

ssh ubuntu@<worker-node> << 'EOF'
sudo ctr -n k8s.io images import /tmp/monitor.tar
sudo ctr -n k8s.io images import /tmp/monitor-api.tar
EOF
