resource "aws_ecr_repository" "airflow" {
  name                 = "airflow-server"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "ingesta" {
  name                 = "ingesta-worker"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "train" {
  name                 = "train-worker"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "backend" {
  name                 = "backend-api"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "frontend" {
  name                 = "frontend-ui"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecr_repository" "ollama" {
  name                 = "ollama-custom"
  image_tag_mutability = "MUTABLE"
}