import os

def read_cgroup_metrics(cgroup_path, pid):
    base = "/host/sys/fs/cgroup"
    full_path = os.path.join(base, cgroup_path.lstrip('/'))
    metrics = {
        "cpu_usage_usec": 0,
        "memory_bytes": 0,
        "io_stats": {},
        "network_rx_bytes": 0,
        "network_tx_bytes": 0
    }

    # cpu.stat
    try:
        with open(os.path.join(full_path, "cpu.stat")) as f:
            for line in f:
                k, v = line.strip().split()
                if k in ["usage_usec", "usage"]:
                    metrics["cpu_usage_usec"] = int(v)
    except Exception as e:
        print(f"[cpu.stat error] {e}")

    # memory.current
    try:
        with open(os.path.join(full_path, "memory.current")) as f:
            metrics["memory_bytes"] = int(f.read().strip())
    except Exception as e:
        print(f"[memory.current error] {e}")

    # io.stat
    try:
        with open(os.path.join(full_path, "io.stat")) as f:
            read_sum = 0
            write_sum = 0
            for line in f:
                print(f"[io.stat raw] {line.strip()}")
                print(f"[io.stat path] {full_path}/io.stat") 
                parts = line.strip().split()
                if not parts:
                    continue
                dev = parts[0]
                for stat in parts[1:]:
                    if "=" in stat:
                        k, v = stat.split("=")
                        key = f"{dev}_{k}"
                        metrics["io_stats"][key] = int(v)
                        if k == "rbytes":
                            read_sum += int(v)
                        elif k == "wbytes":
                            write_sum += int(v)

            metrics["disk_read_bytes"] = read_sum
            metrics["disk_write_bytes"] = write_sum

    except Exception as e:
        print(f"[io.stat error] {e}")


    # network: /proc/<pid>/net/dev
    if pid:
        try:
            with open(f"/host/proc/{pid}/net/dev") as f:
                for line in f:
                    line = line.strip()
                    if ":" not in line or line.startswith("Inter"):
                        continue
                    iface, data = line.split(":")
                    fields = data.strip().split()
                    if len(fields) >= 16:
                        metrics["network_rx_bytes"] += int(fields[0])
                        metrics["network_tx_bytes"] += int(fields[8])
        except Exception as e:
            print(f"[net/dev error] {e}")

    return metrics


# ✅ 노드 전체 리소스 수집
def read_host_metrics():
    base = "/host/sys/fs/cgroup"
    metrics = {
        "cpu_usage_usec": 0,
        "memory_bytes": 0,
        "disk_read_bytes": 0,
        "disk_write_bytes": 0
    }

    # cpu.stat
    try:
        with open(os.path.join(base, "cpu.stat")) as f:
            for line in f:
                k, v = line.strip().split()
                if k in ["usage_usec", "usage"]:
                    metrics["cpu_usage_usec"] = int(v)
    except Exception as e:
        print(f"[host cpu.stat error] {e}")

    # memory.current
    try:
        with open(os.path.join(base, "memory.current")) as f:
            metrics["memory_bytes"] = int(f.read().strip())
    except Exception as e:
        print(f"[host memory.current error] {e}")

    # io.stat
    try:
        with open(os.path.join(base, "io.stat")) as f:
            for line in f:
                print(f"[host io.stat raw] {line.strip()}")
                parts = line.strip().split()
                if not parts:
                    continue
                for stat in parts[1:]:
                    if "=" in stat:
                        k, v = stat.split("=")
                        if k == "rbytes":
                            metrics["disk_read_bytes"] += int(v)
                        elif k == "wbytes":
                            metrics["disk_write_bytes"] += int(v)
    except Exception as e:
        print(f"[host io.stat error] {e}")

    return metrics


if __name__ == '__main__':
    test_path = "/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod123456.slice/cri-containerd-abc.scope"
    test_pid = 12345  # 예시 pid

    print("=== Pod 리소스 측정 ===")
    from pprint import pprint
    pprint(read_cgroup_metrics(test_path, test_pid))

    print("\n=== 노드 전체 리소스 측정 ===")
    pprint(read_host_metrics())