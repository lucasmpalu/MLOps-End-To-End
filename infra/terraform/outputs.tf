output "s3_bucket_name" {
  description = "Nombre del bucket para pasarle a Boto3 en Airflow"
  value       = aws_s3_bucket.ai_data.id 
}

output "ecr_airflow_url" {
  description = "URL para pushear la imagen de Airflow"
  value       = aws_ecr_repository.airflow.repository_url
}

output "ecr_ingesta_url" {
  description = "URL para pushear el worker de Ingesta"
  value       = aws_ecr_repository.ingesta.repository_url
}

output "ecr_train_url" {
  description = "URL para pushear el worker de Entrenamiento"
  value       = aws_ecr_repository.train.repository_url
}

output "ecr_backend_url" {
  description = "URL para pushear la imagen de FastAPI/LangGraph"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_url" {
  description = "URL para pushear la imagen de React/UI"
  value       = aws_ecr_repository.frontend.repository_url
}

output "ecr_ollama_url" {
  description = "URL para pushear la imagen custom de Ollama"
  value       = aws_ecr_repository.ollama.repository_url
}

output "rds_endpoint" {
  description = "URL de conexión a PostgreSQL para el Backend"
  value       = aws_db_instance.postgres_db.endpoint
}

output "eks_cluster_name" {
  description = "Nombre del clúster para configurar el kubectl"
  value       = module.eks.cluster_name
}

output "aws_region" {
  description = "Región de AWS donde está todo desplegado"
  value       = var.aws_region
}