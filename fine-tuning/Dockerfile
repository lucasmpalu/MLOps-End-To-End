# Es normal que esta imagen demore un poco en construirse la primera vez, ya que instala varias dependencias. 
# Pero luego se cacheará y será mucho más rápida.
FROM unsloth/unsloth:latest

 # Esta imagen base tiene un usuario no-root por defecto, pero necesitamos permisos de root para instalar dependencias del sistema
USER root

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY train.py .

ENV MLFLOW_TRACKING_URI="http://mlflow-service:5000"
ENV S3_BUCKET_NAME=""

CMD ["python", "train.py"]