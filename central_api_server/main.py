from flask import Flask, request, jsonify, render_template
import os, json, time
from collections import defaultdict
from datetime import datetime

app = Flask(__name__, template_folder='templates')

DATA_DIR = './data'
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "nodes": os.path.join(DATA_DIR, 'nodes.json'),
    "pods": os.path.join(DATA_DIR, 'pods.json'),
    "namespaces": os.path.join(DATA_DIR, 'namespaces.json'),
    "deployments": os.path.join(DATA_DIR, 'deployments.json'),
}

WINDOW_SIZE = 10  # 10초 단위 윈도우

timeseries = {
    "nodes": defaultdict(dict),
    "pods": defaultdict(dict),
    "namespaces": defaultdict(dict),
    "deployments": defaultdict(dict),
}

# JSON 파일에서 불러오기
def load_all():
    for key in FILES:
        if os.path.exists(FILES[key]):
            with open(FILES[key], 'r') as f:
                try:
                    timeseries[key] = json.load(f)
                except:
                    timeseries[key] = {}

# 저장하기
def save_all():
    for key in timeseries:
        with open(FILES[key], 'w') as f:
            json.dump(timeseries[key], f, indent=2, default=str)

def get_time_bucket(ts):
    return str((int(ts) // WINDOW_SIZE) * WINDOW_SIZE)

def merge_entry(category, key, entry, ts):
    bucket = get_time_bucket(ts)
    if key not in timeseries[category]:
        timeseries[category][key] = {}
    if bucket not in timeseries[category][key]:
        timeseries[category][key][bucket] = []
    timeseries[category][key][bucket].append(entry)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/ingest', methods=['POST'])
def ingest():
    data = request.get_json()
    ts = data.get("timestamp")
    node = data.get("node")

    merge_entry("nodes", node, data["node_data"], ts)
    merge_entry("nodes", "__all__", data["node_data"], ts)

    for pod in data.get("pods", []):
        pod_key = pod["pod"]
        merge_entry("pods", pod_key, pod, ts)
        merge_entry("pods", "__all__", pod, ts)

    for ns in data.get("namespaces", []):
        ns_key = ns["namespace"]
        merge_entry("namespaces", ns_key, ns, ts)
        merge_entry("namespaces", "__all__", ns, ts)

    for dp in data.get("deployments", []):
        dp_key = f"{dp['namespace']}::{dp['deployment']}"
        merge_entry("deployments", dp_key, dp, ts)
        merge_entry("deployments", "__all__", dp, ts)

    save_all()
    return jsonify({"status": "ok"}), 200

def get_recent_entries(category, key, window):
    now = int(time.time())
    cutoff = now - window
    result = []
    buckets = timeseries.get(category, {}).get(key, {})
    for bkt, entries in buckets.items():
        try:
            if int(bkt) >= int(get_time_bucket(cutoff)):
                result.extend(entries)
        except ValueError:
            continue
    return result


@app.route('/api/nodes')
def get_all_nodes():
    window = int(request.args.get("window", 10))
    now = int(time.time())
    cutoff = now - window
    results = []

    for node, buckets in timeseries["nodes"].items():
        if node == "__all__":
            continue

        for bkt_str, entry_list in buckets.items():
            try:
                bkt = int(bkt_str)
                if bkt >= cutoff:
                    for entry in entry_list:
                        e = entry.copy()
                        e["node"] = node
                        e["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(bkt))
                        results.append(e)
            except:
                continue

    return jsonify(results)






@app.route('/api/nodes/<node>')
def get_node(node):
    window = int(request.args.get("window", 10))
    now = int(time.time())
    cutoff_bucket = int(get_time_bucket(now - window))
    results = []

    buckets = timeseries.get("nodes", {}).get(node, {})
    for bkt, entries in buckets.items():
        if int(bkt) >= cutoff_bucket:
            for entry in entries:
                enriched = entry.copy()
                enriched["node"] = node
                enriched["timestamp"] = datetime.fromtimestamp(int(bkt)).strftime("%Y-%m-%d %H:%M:%S")
                results.append(enriched)

    return jsonify(results)


def get_recent_entries(category, key, window):
    cutoff = time.time() - window
    results = []
    for ts, entries in timeseries[category].get(key, {}).items():
        if int(ts) >= int(cutoff):
            for e in entries:
                entry = e.copy()
                # ✅ io 및 timestamp 변환 추가
                entry["disk_read_bytes"] = e.get("disk_read_bytes", 0)
                entry["disk_write_bytes"] = e.get("disk_write_bytes", 0)
                entry["timestamp"] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
                results.append(entry)
    return results

@app.route('/api/nodes/<node>/pods')
def get_node_pods(node):
    window = int(request.args.get("window", 10))
    results = []
    cutoff = time.time() - window

    for pod_key, buckets in timeseries["pods"].items():
        for ts, entries in buckets.items():
            try:
                if int(ts) >= int(cutoff):
                    for e in entries:
                        if e.get("node") == node:
                            pod = e.copy()
                            # ✅ io 및 timestamp 변환
                            pod["disk_read_bytes"] = pod.get("disk_read_bytes", 0)
                            pod["disk_write_bytes"] = pod.get("disk_write_bytes", 0)
                            pod["timestamp"] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
                            results.append(pod)
            except:
                continue
    return jsonify(results)

@app.route('/api/pods')
def get_all_pods():
    window = int(request.args.get("window", 10))
    return jsonify(get_recent_entries("pods", "__all__", window))

@app.route('/api/pods/<pod>')
def get_pod(pod):
    window = int(request.args.get("window", 10))
    return jsonify(get_recent_entries("pods", pod, window))

@app.route('/api/namespaces')
def get_all_namespaces():
    window = int(request.args.get("window", 10))
    return jsonify(get_recent_entries("namespaces", "__all__", window))

@app.route('/api/namespaces/<ns>')
def get_namespace(ns):
    window = int(request.args.get("window", 10))
    return jsonify(get_recent_entries("namespaces", ns, window))

@app.route('/api/namespaces/<ns>/pods')
def get_namespace_pods(ns):
    window = int(request.args.get("window", 10))
    results = []
    cutoff = time.time() - window
    for pod_key, buckets in timeseries["pods"].items():
        for ts, entries in buckets.items():
            try:
                if int(ts) >= int(cutoff):
                    for e in entries:
                        if e.get("namespace") == ns:
                            pod = e.copy()
                            # ✅ io 및 timestamp 변환
                            pod["disk_read_bytes"] = pod.get("disk_read_bytes", 0)
                            pod["disk_write_bytes"] = pod.get("disk_write_bytes", 0)
                            pod["timestamp"] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
                            results.append(pod)
            except:
                continue
    return jsonify(results)

@app.route('/api/namespaces/<ns>/deployments')
def get_namespace_deployments(ns):
    window = int(request.args.get("window", 10))
    results = []
    cutoff = time.time() - window
    for dp_key, buckets in timeseries["deployments"].items():
        if not dp_key.startswith(f"{ns}::"):
            continue
        for ts, entries in buckets.items():
            try:
                if int(ts) >= int(cutoff):
                    for e in entries:
                        entry = e.copy()
                        entry["disk_read_bytes"] = e.get("disk_read_bytes", 0)
                        entry["disk_write_bytes"] = e.get("disk_write_bytes", 0)
                        entry["timestamp"] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
                        results.append(entry)
            except:
                continue
    return jsonify(results)

@app.route('/api/namespaces/<ns>/deployments/<dp>')
def get_deployment(ns, dp):
    window = int(request.args.get("window", 10))
    key = f"{ns}::{dp}"
    return jsonify(get_recent_entries("deployments", key, window))

@app.route('/api/namespaces/<ns>/deployments/<dp>/pods')
def get_deployment_pods(ns, dp):
    window = int(request.args.get("window", 10))
    results = []
    cutoff = time.time() - window
    for pod_key, buckets in timeseries["pods"].items():
        for ts, entries in buckets.items():
            try:
                if int(ts) >= int(cutoff):
                    for e in entries:
                        if (
                            e.get("namespace") == ns and
                            e.get("deployment") == dp
                        ):
                            entry = e.copy()
                            entry["disk_read_bytes"] = e.get("disk_read_bytes", 0)
                            entry["disk_write_bytes"] = e.get("disk_write_bytes", 0)
                            entry["timestamp"] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
                            results.append(entry)
            except:
                continue
    return jsonify(results)

if __name__ == '__main__':
    load_all()
    app.run(host='0.0.0.0', port=8082)