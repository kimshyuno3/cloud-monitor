# cloud-monitor
쿠버네티스를 활용한 클라우드 모니터링 서비스 개발


1. 프로젝트 개요
쿠버네티스 클러스터의 리소스 사용량을 데몬셋을 사용하여 수집하고, 이를 시계열 기반으로 저
장 및 조회할 수 있는 모니터링 시스템을 구축한다.
<img width="526" height="105" alt="image" src="https://github.com/user-attachments/assets/3ecfeead-9ac4-47ad-a1a6-6c1ee65b1ed8" />
    1. Agent (DaemonSet)
  • 각 노드에 배포되어 10초마다 해당 노드의 메타데이터와 리소스를 수집.
  • 수집 항목: CPU, Memory, Disk IO, Network, Pod/Namespace/Deployment 정보
  • 수집 방법: /proc, /sys/fs/cgroup 파싱
  • 수집 후 중앙 API 서버에 JSON 형태로 전송
    2. 중앙 API 서버 (Flask)
  • 수집된 리소스를 노드/파드/네임스페이스/디플로이먼트 단위로 시계열 저장
  • 저장 방식: JSON 파일(nodes.json, pods.json 등)에 윈도우 버킷 단위로 저장
  • 제공 API:
  o POST /api/ingest : 수집 데이터 저장
  o GET /api/nodes, /api/pods, ...
  o GET /api/nodes/<node> :
  o GET /api/nodes/<node>/pods :
  o GET /api/namespaces, /deployments, ... :
  o 등등
  o 시계열 조회는 모든 api에서 가능하도록 구현했습니다.

2. 코드 제출물 디렉토리 구조
 <img width="565" height="549" alt="image" src="https://github.com/user-attachments/assets/717e146e-7b89-4b7c-8551-78d160bfc54a" />

3. 각 기능 구현 내용 설명
 <img width="630" height="426" alt="image" src="https://github.com/user-attachments/assets/e8369eff-c7ba-453a-8b00-2dd3f7b0836c" />

   3.1 agent/metadata_collector.py
    이 스크립트는 쿠버네티스 클러스터의 각 pod의 메타데이터를 수집하기 위한 목적으로
    작성되었습니다. 주요 목적은 pod와 container의 식별 정보 및 cgroup 경로를 추출하는
    것입니다.
    1. find_pause_pids()
    • /host/proc 경로를 탐색하여 pause 컨테이너의 PID 목록을 탐색합니다.
    • 각 /cmdline에 "pause" 문자열이 있는지 확인하여 해당 PID를 수집합니다.
    2. get_pod_uid_from_pid(pid)
    • 해당 PID의 /proc/[pid]/cgroup 파일을 읽어 kubepods 경로에서 Pod UID 추출.
    • _ 문자를 -로 변환하여 UID 형식 표준화.
    3. find_pod_id_by_uid(uid)
    • crictl pods -o json 명령어를 통해 전체 pod 목록을 가져오고, UID를 기준으로
    Pod ID를 매칭합니다.
    4. get_pause_container_id(pod_id)
    • crictl inspectp <pod_id> 명령어로 pause 컨테이너의 Container ID(sandbox ID)
    를 추출합니다.
    5. get_metadata_from_crictl(pod_id)
    • pod의 이름, 네임스페이스, deployment(app label)를 crictl로 조회하여 메타데이터
    구성.
    6. get_cgroup_path_from_pid(pid)
    • /proc/[pid]/cgroup 파일을 읽고, cgroup 경로를 추출합니다.
    7. collect_metadata()
    • 결과는 각 pod에 대해 다음 정보를 포함:
    o pod_name, namespace, deployment
    o pod_uid, pod_id, container_id
    o PID, cgroup_path
    pause PID 탐색 → Pod UID 추출 → Pod ID 조회 → Container ID 추출 → 메타데이터
    수집 → 최종 구조화된 결과 반환
    
  3.2 agent/resource_collector.py
    이 스크립트는 Kubernetes 노드에서 pod별 및 노드 전체 리소스 사용량을 수집하기 위
    한 목적으로 작성되었습니다. 주요 수집 대상은 CPU 사용량, 메모리 사용량, 디스크 I/O,
    네트워크 I/O입니다.
    사용 목적
    • Pod 단위 리소스 모니터링:
    에이전트가 각 pod의 리소스를 추적하여 시계열로 기록
    • 노드 전체 리소스 상태 파악:
    중앙 API 서버에 주기적으로 전송하여 클러스터 상태 분석에 활용
    1. read_cgroup_metrics(cgroup_path, pid)
    목적: 특정 pod의 cgroup 경로 및 PID를 기반으로 리소스 사용량 수집
    수집 항목
    • CPU 사용량 (microsecond 단위):
    /sys/fs/cgroup/[cgroup_path]/cpu.stat → usage_usec 또는 usage
    • 메모리 사용량 (bytes):
    /sys/fs/cgroup/[cgroup_path]/memory.current
    • 디스크 I/O (bytes):
    /sys/fs/cgroup/[cgroup_path]/io.stat
    → rbytes, wbytes를 device 단위로 파싱
    → 총합을 disk_read_bytes, disk_write_bytes로 저장
    • 네트워크 I/O (bytes):
    /proc/[pid]/net/dev 파일을 통해 인터페이스별 수신/송신 바이트 추출
    → network_rx_bytes, network_tx_bytes
    2. read_host_metrics()
    목적: 노드 전체(cgroup root)의 리소스 사용량 측정
    수집 항목
    • /sys/fs/cgroup/cpu.stat
    • /sys/fs/cgroup/memory.current
    • /sys/fs/cgroup/io.stat
  
  3.3 agent/main.py
    이 모듈은 Kubernetes 클러스터의 각 노드에 DaemonSet으로 배포되는 에이전트로, 주
    기적으로 리소스를 수집하고 중앙 API 서버에 전송합니다.
    1. collect_node_data()
    목적:
    각 pod의 리소스를 기반으로 다음 수준으로 집계:
    • Pod 단위
    • Namespace 단위
    • Deployment 단위
    • 노드 전체
    동작 흐름:
    1. collect_metadata() 호출 → pause PID 기반 pod 정보 수집
    2. 각 pod에 대해 read_cgroup_metrics() 호출 → 개별 리소스 측정
    3. Pod 정보 저장
    4. Namespace/Deployment 기준으로 집계
    o defaultdict로 pod별 metric을 묶고, summarize() 함수로 합산
    2. send_to_server(data)
    • 위에서 수집한 데이터를 중앙 API 서버(환경 변수로 주소 주입)로 전송
    • 요청 실패 시 에러 출력
    3. run(interval=10)
    • 10초마다: 리소스 수집 → 중앙 서버 전송(무한 루프로 동작)

  3.4 central_api_server/main.py
    이 서버는 쿠버네티스 노드에서 전송된 리소스 사용량 데이터를 수신하고, 이를 시계열
    단위로 저장 및 제공하는 기능을 수행합니다. 모든 시계열에 대해 모두 구현하였습니다.
     시계열 구조: 10초 단위 버킷으로 집계 (타임윈도우 병합)
    API 기능: 실시간 데이터 수신 및 조회
    각 데이터 항목은 다음 4가지로 분류되어 저장됨:
    • nodes.json: 노드 전체 리소스
    • pods.json: 개별 Pod 리소스
    • namespaces.json: 네임스페이스 단위 집계
    • deployments.json: 디플로이먼트 단위 집계
    수신 API
    POST /api/ingest
    • 노드 에이전트가 10초마다 리소스 데이터를 전송
    • 수신한 데이터를 카테고리(key) - 버킷(timestamp) 구조로 저장
    • __all__ 키를 통해 전체 클러스터 기준 데이터도 함께 저장됨
    타임윈도우 집계 방식
    • 모든 timestamp는 10초 단위 버킷으로 변환 (get_time_bucket())
    • 하나의 버킷 내에 여러 entry가 리스트로 저장
    • 조회 시 현재 시간에서 window 이전까지의 버킷만 필터링
    
  3.5 monitor-api.yaml
    이 YAML 파일은 리소스 모니터링 시스템에서 사용하는 중앙 API 서버(Flask)를
    Kubernetes에 배포하기 위한 Deployment + Service 정의입니다.
  3.6monitor.yaml
    이 YAML은 Kubernetes 클러스터의 모든 노드에 배포되는 리소스 수집 에이전트(Monit
    를 정의한 DaemonSet입니다. 각 노드에서 컨테이너 및 시스템 리소스를 주기적으로 수
    집하고, 중앙 API 서버로 전송합니다.

4. 개발환경 구축, 빌드, 배포
4.1 개발환경 구축
kubectl 만 설치해도 OK
4.2 빌드
4.3 배포
chmod +x deploy
./deploy

참고
워커노드에서의 정보도 확인하고싶다면, 이미지 다시 다운받아줘야함.
scp monitor.tar ubuntu@ <worker node>:/tmp/ : 워커노드로 이미지 보내기
scp monitor-api.tar ubuntu@ <worker node>:/tmp/
sudo ctr -n k8s.io images import /tmp/monitor.tar : 이미지 받음
sudo ctr -n k8s.io images import /tmp/monitor-api.tar : 이미지 받음

    
  
