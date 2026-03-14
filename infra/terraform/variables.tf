variable "project_name" {
  description = "El nombre base del proyecto"
  type        = string
  default     = "lostsys"
}

variable "environment" {
  description = "El entorno a desplegar (dev, prod)"
  type        = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  description = "El bloque de IPs para la red virtual"
  type        = string
}


variable "db_instance_class" {
  description = "El tamaño de la máquina de la base de datos"
  type        = string
}

variable "db_password" {
  description = "Contraseña para la base de datos RDS"
  type        = string
  sensitive   = true
}