resource "aws_db_instance" "postgres_db" {
  identifier           = "${var.project_name}-db-${var.environment}"
  engine               = "postgres"
  engine_version       = "15.3"
  instance_class       = var.db_instance_class
  allocated_storage    = 20
  
  db_name              = "lostsys_db"
  username             = "admin_lostsys"
  password             = var.db_password
  
  db_subnet_group_name   = aws_db_subnet_group.db_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  
  publicly_accessible  = false
  skip_final_snapshot  = true
}

