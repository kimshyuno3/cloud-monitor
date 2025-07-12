☁️ cloud-monitor
쿠버네티스를 활용한 클라우드 리소스 모니터링 시스템
Kubernetes 클러스터의 리소스를 DaemonSet으로 수집하고, 시계열 기반으로 저장/조회할 수 있는 모니터링 서비스입니다.

📌 1. 프로젝트 개요
<img width="526" height="105" alt="architecture" src="https://github.com/user-attachments/assets/3ecfeead-9ac4-47ad-a1a6-6c1ee65b1ed8" />
Agent (DaemonSet)

각 노드에 배포되어 10초마다 리소스 및 메타데이터 수집

수집 항목: CPU, Memory, Disk IO, Network, Pod, Namespace, Deployment

수집 방법: /proc, /sys/fs/cgroup 파싱

JSON 형태로 중앙 API 서버에 전송

중앙 API 서버 (Flask)

수집 데이터를 시계열(JSON 파일)로 저장 (nodes.json, pods.json, 등)

단위: Node / Pod / Namespace / Deployment

10초 단위 타임윈도우 버킷 구조로 저장

제공 API 예시:

POST /api/ingest: 데이터 수신

GET /api/nodes, /api/pods, /api/namespaces, /api/deployments

GET /api/nodes/<node>, /api/nodes/<node>/pods 등

모든 API에서 시계열 조회 가능

📁 2. 디렉토리 구조
<img width="565" height="549" alt="structure" src="https://github.com/user-attachments/assets/717e146e-7b89-4b7c-8551-78d160bfc54a" />
⚙️ 3. 주요 기능 설명
📍 agent/metadata_collector.py
각 pod의 메타데이터 수집: pod UID, container ID, namespace, deployment 등

흐름: pause PID → Pod UID → Pod ID → Container ID → 메타데이터 추출

📍 agent/resource_collector.py
리소스 수집 항목:

CPU: /sys/fs/cgroup/.../cpu.stat

Memory: /memory.current

Disk IO: /io.stat

Network: /proc/[pid]/net/dev

📍 agent/main.py
10초마다 수집 주기

단위별 집계:

Pod → Namespace → Deployment → Node

중앙 API 서버로 전송

📍 central_api_server/main.py
수신한 리소스 데이터를 시계열 버킷으로 저장

파일 단위 저장:

nodes.json, pods.json, namespaces.json, deployments.json

타임윈도우 병합 처리

10초 단위로 정규화하여 저장

__all__ 키를 통해 클러스터 전체 요약도 저장

📍 monitor.yaml
DaemonSet 정의 (각 노드에서 리소스 수집 및 전송)

📍 monitor-api.yaml
중앙 API 서버의 Deployment + Service 정의

🧪 4. 개발환경 구축 및 배포
📌 4.1 개발환경
kubectl 설치만으로 개발 및 테스트 가능

📌 4.2 빌드 & 배포
bash
복사
편집
chmod +x deploy
./deploy
📌 4.3 이미지 수동 배포 (Worker Node)
bash
복사
편집
# 워커 노드로 이미지 전송
scp monitor.tar ubuntu@<worker-node>:/tmp/
scp monitor-api.tar ubuntu@<worker-node>:/tmp/

# 이미지 가져오기
ssh ubuntu@<worker-node>
sudo ctr -n k8s.io images import /tmp/monitor.tar
sudo ctr -n k8s.io images import /tmp/monitor-api.tar
📎 참고
리소스 수집 간격: 10초 주기

저장 구조: JSON 파일 기반 시계열 저장 (버킷 단위 집계)

확장성 고려: 추후 Prometheus, TimescaleDB 등으로 교체 가능

