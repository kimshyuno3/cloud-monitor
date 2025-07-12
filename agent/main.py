import os
import time
import socket
import requests
from metadata_collector import collect_metadata
from resource_collector import read_cgroup_metrics
from collections import defaultdict

API_SERVER = os.environ.get("CENTRAL_API_SERVER", "http://central-api-service.kube-system.svc.cluster.local:8082/api/ingest")

def get_node_name():
    return socket.gethostname()

def read_metrics_safe(cgroup_path, pid):
    try:
        return read_cgroup_metrics(cgroup_path, pid)
    except Exception:
        return {
            "cpu_usage_usec": 0,
            "memory_bytes": 0,
            "io_stats": {"read_bytes": 0, "write_bytes": 0},
            "network_rx_bytes": 0,
            "network_tx_bytes": 0
        }

def collect_node_data():
    pod_list = collect_metadata()
    node_name = get_node_name()
    timestamp = int(time.time())

    pods_data = []
    ns_map = defaultdict(list)
    dp_map = defaultdict(list)

    for pod in pod_list:
        metrics = read_metrics_safe(pod['cgroup_path'], pod['pid'])
        pod_info = {
            "timestamp": timestamp,
            "node": node_name,
            "namespace": pod['namespace'],
            "deployment": pod.get('deployment', ''),
            "pod": pod['pod_name'],
            **metrics
        }
        pods_data.append(pod_info)
        ns_map[pod['namespace']].append(metrics)
        dp_map[(pod['namespace'], pod.get('deployment', ''))].append(metrics)

    def summarize(metric_list):
        agg = {
            "cpu_millicores": 0,
            "memory_bytes": 0,
            "disk_read_bytes": 0,
            "disk_write_bytes": 0,
            "network_rx_bytes": 0,
            "network_tx_bytes": 0
        }
        for m in metric_list:
            agg["cpu_millicores"] += m.get('cpu_usage_usec', 0) // 1000
            agg["memory_bytes"] += m.get('memory_bytes', 0)
            agg["disk_read_bytes"] += m.get('io_stats', {}).get('read_bytes', 0)
            agg["disk_write_bytes"] += m.get('io_stats', {}).get('write_bytes', 0)
            agg["network_rx_bytes"] += m.get('network_rx_bytes', 0)
            agg["network_tx_bytes"] += m.get('network_tx_bytes', 0)
        return agg

    namespaces_data = []
    for ns, metrics in ns_map.items():
        agg = summarize(metrics)
        namespaces_data.append({
            "timestamp": timestamp,
            "namespace": ns,
            "node": node_name,
            **agg
        })

    deployments_data = []
    for (ns, dp), metrics in dp_map.items():
        agg = summarize(metrics)
        deployments_data.append({
            "timestamp": timestamp,
            "namespace": ns,
            "deployment": dp,
            "node": node_name,
            **agg
        })

    node_agg = summarize([read_metrics_safe(p['cgroup_path'], p['pid']) for p in pod_list])

    return {
        "timestamp": timestamp,
        "node": node_name,
        "node_data": node_agg,
        "pods": pods_data,
        "namespaces": namespaces_data,
        "deployments": deployments_data
    }

def send_to_server(data):
    try:
        res = requests.post(API_SERVER, json=data, timeout=3)
        print(f"[{data['timestamp']}] Sent to API server - status {res.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to send data: {e}")

def run(interval=10):
    while True:
        data = collect_node_data()
        send_to_server(data)
        time.sleep(interval)

if __name__ == "__main__":
    run()
