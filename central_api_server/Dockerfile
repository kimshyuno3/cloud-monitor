# central_api_server/Dockerfile
FROM python:3.10-slim

WORKDIR /app/central_api_server      # 🔥 핵심
COPY . .

RUN pip install --no-cache-dir flask
CMD ["python", "main.py"]
