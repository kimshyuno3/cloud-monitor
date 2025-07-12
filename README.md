# ☁️ cloud-monitor
쿠버네티스를 활용한 **클라우드 리소스 모니터링 서비스**

Kubernetes 클러스터의 리소스를 DaemonSet으로 수집하고, 시계열(JSON)로 저장·조회할 수 있는 경량 모니터링 시스템입니다.

---

## 1. 프로젝트 개요

![architecture](https://github.com/user-attachments/assets/3ecfeead-9ac4-47ad-a1a6-6c1ee65b1ed8)

### 1.1 Agent (DaemonSet)
- 각 노드에 배포되어 **10 초마다** 해당 노드의 메타데이터·리소스 수집  
- 수집 항목: CPU / Memory / Disk IO / Network / Pod · Namespace · Deployment 정보  
- 수집 방법: `/proc`, `/sys/fs/cgroup` 파싱  
- 수집 후 중앙 API 서버로 JSON 전송

### 1.2 중앙 API 서버 (Flask)
- 수집 데이터를 Node / Pod / Namespace / Deployment 단위로 시계열 저장  
- 저장 형식: `nodes.json`, `pods.json`, `namespaces.json`, `deployments.json` (10 초 버킷)  
- 주요 API  
  - `POST /api/ingest` – 데이터 수신  
  - `GET /api/nodes`, `/api/pods`, `/api/namespaces`, `/api/deployments`  
  - `GET /api/nodes/<node>`, `/api/nodes/<node>/pods`  
  - **모든 API에서 시계열 조회 지원**

---

## 2. 코드 디렉토리 구조

![structure](https://github.com/user-attachments/assets/717e146e-7b89-4b7c-8551-78d160bfc54a)

cloud-monitor/
├─ agent/
│ ├─ metadata_collector.py
│ ├─ resource_collector.py
│ └─ main.py
├─ central_api_server/
│ └─ main.py
├─ k8s/
│ ├─ monitor.yaml # DaemonSet
│ └─ monitor-api.yaml # API Deployment + Service
└─ deploy # 배포 스크립트

markdown
복사
편집

---

## 3. 주요 기능 설명

### 3.1 `agent/metadata_collector.py`
pause PID → Pod UID → Pod ID → Container ID 순으로 추적해 다음 메타데이터를 수집합니다.

| key | 설명 |
|-----|------|
| `pod_name` / `namespace` / `deployment` | 식별 메타 |
| `pod_uid`, `container_id`               | UID, sandbox ID |
| `PID`, `cgroup_path`                    | 리소스 경로 기준 |

### 3.2 `agent/resource_collector.py`
| 항목 | 수집 위치 | 지표 |
|------|-----------|------|
| CPU   | `cpu.stat`            | usage\_usec |
| Memory| `memory.current`      | bytes |
| Disk  | `io.stat`             | `disk_read_bytes`, `disk_write_bytes` |
| Net   | `/proc/[pid]/net/dev` | `network_rx_bytes`, `network_tx_bytes` |

### 3.3 `agent/main.py`
1. **10 초 루프**로 메타 + 리소스 수집  
2. Pod → Namespace → Deployment → Node 단위로 집계  
3. 중앙 API 서버에 전송

### 3.4 `central_api_server/main.py`
- 모든 지표를 **10 초 버킷**으로 병합 저장  
- `_ _all__` 키로 클러스터 전체 집계 유지  
- 실시간 조회 API 제공

### 3.5 `k8s/monitor-api.yaml`
Flask API를 Kubernetes에 배포하는 Deployment + Service 정의

### 3.6 `k8s/monitor.yaml`
Agent DaemonSet 정의 (모든 노드에 자동 배포)

---

## 4. 개발환경·빌드·배포

### 4.1 개발환경
- **kubectl**만 설치되어 있으면 테스트 가능

### 4.2 빌드 & 배포 + 4.3 이미지 수동 배포 (Worker Node)

### ── 1) 클러스터 배포 ───────────────────────────
chmod +x deploy
./deploy

### ── 2) 워커 노드에 이미지 전송 + 가져오기 ──────
scp monitor.tar monitor-api.tar ubuntu@<worker-node>:/tmp/

ssh ubuntu@<worker-node> << 'EOF'
sudo ctr -n k8s.io images import /tmp/monitor.tar
sudo ctr -n k8s.io images import /tmp/monitor-api.tar
EOF

