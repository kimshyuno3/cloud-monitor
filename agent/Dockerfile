FROM python:3.10-slim

WORKDIR /app

COPY main.py .
COPY metadata_collector.py .
COPY resource_collector.py . 
RUN mkdir -p /etc
COPY crictl.yaml /etc/crictl.yaml
RUN ls -al /app  

RUN pip install flask psutil requests

# crictl 설치 (필요한 바이너리만 다운받음)
RUN apt-get update && apt-get install -y wget tar && \
    wget -q https://github.com/kubernetes-sigs/cri-tools/releases/download/v1.29.0/crictl-v1.29.0-linux-amd64.tar.gz && \
    tar -C /usr/local/bin -xzf crictl-v1.29.0-linux-amd64.tar.gz && \
    chmod +x /usr/local/bin/crictl && \
    rm crictl-v1.29.0-linux-amd64.tar.gz


CMD ["python", "main.py"]