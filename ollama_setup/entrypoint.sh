#!/bin/bash

echo "Iniciando servidor de Ollama..."
ollama serve &

sleep 5

echo "Buscando el último entrenamiento en S3..."

LATEST_RUN=$(aws s3 ls s3://${S3_BUCKET_NAME}/mlflow-artifacts/1/ | sort | tail -n 1 | awk '{print $2}' | sed 's/\///g')

if [ -z "$LATEST_RUN" ]; then
    echo "AVISO: No se encontró entrenamiento. Levantando Ollama base para no bloquear el pod."
    # En lugar de exit 1, simplemente dejamos que el contenedor siga vivo
    ollama pull llama3.2 # O el modelo base que prefieras
else
    echo "Descargando pesos del modelo desde el RUN: $LATEST_RUN"
    aws s3 cp s3://${S3_BUCKET_NAME}/mlflow-artifacts/1/${LATEST_RUN}/artifacts/modelo_final/ ./pesos_descargados_de_s3/ --recursive
    ollama create Lucas-Palu-Llama-3.2-3B-trained -f Modelfile
fi

echo "Descargando pesos del modelo desde el RUN: $LATEST_RUN"
aws s3 cp s3://${S3_BUCKET_NAME}/mlflow-artifacts/1/${LATEST_RUN}/artifacts/modelo_final/ ./pesos_descargados_de_s3/ --recursive

echo "Construyendo el modelo Lucas-Palu-Llama-3.2-3B-trained..."
ollama create Lucas-Palu-Llama-3.2-3B-trained -f Modelfile

echo "¡Modelo registrado exitosamente!"
ollama list

wait