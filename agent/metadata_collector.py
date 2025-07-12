import os
import json
import subprocess
import re

PROC_DIR = "/host/proc"

def find_pause_pids():
    pause_pids = []
    for pid in os.listdir(PROC_DIR):
        if not pid.isdigit():
            continue
        try:
            with open(f"{PROC_DIR}/{pid}/cmdline", "rb") as f:
                cmd = f.read().decode().replace('\x00', ' ')
                if 'pause' in cmd:
                    print(f"[pause] Found pause PID: {pid} -> {cmd}")
                    pause_pids.append(pid)
        except:
            continue
    return pause_pids

def get_pod_uid_from_pid(pid):
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            for line in f:
                if "kubepods" in line:
                    match = re.search(r"pod([0-9a-fA-F_\-]{36,})", line)
                    if match:
                        raw_uid = match.group(1)
                        # 언더스코어 → 하이픈으로 변환
                        uid = raw_uid.replace("_", "-")
                        print(f"[cgroup] PID {pid} → UID: {uid}")
                        return uid
    except Exception as e:
        print(f"[cgroup] error for PID {pid}: {e}")
    print(f"[skip] No UID for PID {pid}")
    return None

def find_pod_id_by_uid(uid):
    try:
        result = subprocess.run(["crictl", "pods", "-o", "json"], capture_output=True, text=True)
        data = json.loads(result.stdout)
        for pod in data["items"]:
            # dash를 모두 제거해서 비교 (포맷 불일치 방지)
            if pod["metadata"]["uid"].replace("-", "") == uid.replace("-", ""):
                print(f"[pod_id] UID {uid} → Pod ID: {pod['id']}")
                return pod["id"]
    except Exception as e:
        print(f"[pod_id] crictl error: {e}")
    print(f"[skip] No pod_id for UID {uid}")
    return None


def get_pause_container_id(pod_id):
    try:
        result = subprocess.run(["crictl", "inspectp", pod_id], capture_output=True, text=True)
        data = json.loads(result.stdout)

        pause_id = data.get("status", {}).get("id")
        if pause_id:
            print(f"[pause_container] Pod ID {pod_id} → Container ID: {pause_id}")
            return pause_id
        else:
            print(f"[pause_container] No sandbox ID found in Pod ID {pod_id}")
    except Exception as e:
        print(f"[pause_container] inspectp error: {e}")
    return None




def get_metadata_from_crictl(pod_id):
    try:
        result = subprocess.run(["crictl", "inspectp", pod_id], capture_output=True, text=True)
        data = json.loads(result.stdout)
        labels = data.get("info", {}).get("config", {}).get("labels", {})
        pod_name = labels.get("io.kubernetes.pod.name", "")
        namespace = labels.get("io.kubernetes.pod.namespace", "")
        print(f"[metadata] {pod_name} / {namespace}")
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "deployment": labels.get("app", "unknown")
        }
    except Exception as e:
        print(f"[metadata] inspectp error: {e}")
        return None

def get_cgroup_path_from_pid(pid):
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) == 3:
                    return parts[2]
    except Exception as e:
        print(f"[cgroup_path] Failed for PID {pid}: {e}")
    return None

def collect_metadata():
    result = []
    for pid in find_pause_pids():
        pod_uid = get_pod_uid_from_pid(pid)
        if not pod_uid:
            print(f"[skip] No UID for PID {pid}")
            continue

        pod_id = find_pod_id_by_uid(pod_uid)
        if not pod_id:
            print(f"[skip] No pod_id for UID {pod_uid}")
            continue

        container_id = get_pause_container_id(pod_id)
        if not container_id:
            print(f"[skip] No container_id for Pod ID {pod_id}")
            continue

        metadata = get_metadata_from_crictl(container_id)
        if not metadata:
            print(f"[skip] No metadata for Container ID {container_id}")
            continue

        cgroup_path = get_cgroup_path_from_pid(pid)
        if not cgroup_path:
            continue

        result.append({
            **metadata,
            "pid": int(pid),
            "pod_uid": pod_uid,
            "pod_id": pod_id,
            "container_id": container_id,
            "cgroup_path": cgroup_path
        })

    return result


# 실행
if __name__ == "__main__":
    from pprint import pprint
    pprint(collect_metadata())
