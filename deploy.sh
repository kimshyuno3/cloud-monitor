#!/bin/bash

echo "🛠️  Building central API server image..."
docker build -t monitor-api:latest ./central_api_server

echo "🛠️  Building resource agent image..."
docker build -t monitor:latest ./agent

echo "🚀  Applying central API server deployment..."
kubectl delete -f monitor-api.yaml
kubectl apply -f monitor-api.yaml

echo "🚀  Applying resource agent DaemonSet..."
kubectl delete -f monitor.yaml
kubectl apply -f monitor.yaml

echo "✅ All components deployed successfully."

# 1. 이미지 저장
docker save monitor:latest -o monitor.tar
docker save monitor-api:latest -o monitor-api.tar

# 2. 대상 노드로 전송
scp monitor.tar 10.0.10.88:/tmp/
scp monitor-api.tar 10.0.10.88:/tmp/

# 3. 대상 노드에서 로드

sudo ctr -n k8s.io images import /tmp/monitor.tar
sudo ctr -n k8s.io images import /tmp/monitor-api.tar
# 4. 리소스 재배포
kubectl delete -f monitor.yaml
kubectl apply -f monitor.yaml

kubectl delete -f monitor-api.yaml
kubectl apply -f monitor-api.yaml

kubectl apply -f central-api-service.yaml

 kubectl port-forward -n kube-system svc/central-api-service 8082:8082