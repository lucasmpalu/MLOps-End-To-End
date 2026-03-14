FROM python:3.11-slim

USER root

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt

COPY dag_tasks.py .

CMD ["python", "dag_tasks.py"]

