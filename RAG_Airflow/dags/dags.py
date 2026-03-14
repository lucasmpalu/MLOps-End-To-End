import os
from airflow import DAG 
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from dag_tasks import check_new_pdfs_s3, extract_and_load_s3
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from kubernetes.client import models as k8s

default_args = {
    'owner': 'lucas_palu',
    'start_date': datetime(2026, 2, 25),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    
}

ECR_REGISTRY = "559979279038.dkr.ecr.us-east-1.amazonaws.com"
name_index = os.get

with DAG('pipeline_rag_lostsys',
         default_args=default_args, 
         schedule_interval='@daily',     
         catchup=False) as dag:

    task1 = PythonOperator(
        task_id='identificar_nuevos_pdf',
        python_callable=check_new_pdfs_s3,
        provide_context=True
    )

    task2 = KubernetesPodOperator(
        task_id='procesar_y_cargar_rag',
        name="worker-ingesta-pdf",
        namespace="airflow",
        image=os.getenv("DOCKER_IMAGE_INGESTA", "ingesta-pdf:latest"),
        get_logs=True, 

        env_vars={
            k8s.V1EnvVar(name="ARCHIVOS_NUEVOS", value="{{ task_instance.xcom_pull(task_ids='identificar_nuevos_pdf') }}"),
            k8s.V1EnvVar(name="INDEX_NAME", value=name_index),
            k8s.V1EnvVar(name="DATABASE_URL", value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name="rds-secrets", key="url"))),
            k8s.V1EnvVar(name="OPENAI_API_KEY", value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name="openai-secrets", key="api-key")))
    },
        is_delete_operator_pod=True
    )
    task1 >> task2


with DAG(
    '2_entrenamiento_llama_mlflow',
    default_args=default_args,
    schedule_interval=None,
    tags=['Lostsys', 'Fine-Tuning', 'GPU'],
) as dag_entrenamiento:

    tarea_entrenar = KubernetesPodOperator(
        task_id="entrenar_llama_unsloth",
        name="train-llama-pod",
        namespace="airflow",
        image=f"{ECR_REGISTRY}/train-worker:latest",
        image_pull_policy="Always",
        env_vars=[
            k8s.V1EnvVar(name="OPENAI_API_KEY", value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name="openai-secrets", key="api-key"))),
            k8s.V1EnvVar(name="AWS_ACCESS_KEY_ID", value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name="aws-v3-credentials", key="access-key"))),
            k8s.V1EnvVar(name="AWS_SECRET_ACCESS_KEY", value_from=k8s.V1EnvVarSource(secret_key_ref=k8s.V1SecretKeySelector(name="aws-v3-credentials", key="secret-key"))),
            k8s.V1EnvVar(name="S3_BUCKET_NAME", value="mlops_data_lucas_palu"),
            k8s.V1EnvVar(name="MLFLOW_TRACKING_URI", value="http://mlflow-service:5000"),
        ],
        container_resources=k8s.V1ResourceRequirements(
            limits={"nvidia.com/gpu": "1"}
        ),
        
        startup_timeout_seconds=600, 
        is_delete_operator_pod=True,
        get_logs=True,
    )