resource "aws_s3_bucket" "ai_data" {

  bucket = "mlops-ai-data-lucas-palu"

  tags = {
    Name        = "Data Bucket"
    Environment = "Dev"
  }

} 
