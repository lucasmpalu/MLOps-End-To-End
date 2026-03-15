module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${var.project_name}-cluster-${var.environment}"
  cluster_version = "1.29"

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true

eks_managed_node_groups = {

    nodos_generales = {
      min_size       = 1
      max_size       = 3
      desired_size   = 2
      instance_types = ["t3.micro"] 
      capacity_type  = "ON_DEMAND"

      labels = {
        entorno = "general"
      }
    }

    nodos_gpu = {
      min_size       = 0
      max_size       = 2
      desired_size   = 1
      instance_types = ["t3.large"]

      capacity_type  = "SPOT" 

      labels = {
        entorno = "ia-gpu"
      }

      taints = {
        gpu_exclusiva = {
          key    = "recurso"
          value  = "gpu"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }

  enable_cluster_creator_admin_permissions = true
}


output "cluster_name" {
  value = module.eks.cluster_name
}

resource "kubernetes_namespace" "airflow" {
  metadata {
    name = "airflow"
  }
  depends_on = [module.eks]
}

resource "kubernetes_namespace" "mlflow" {
  metadata {
    name = "mlflow"
  }
  depends_on = [module.eks]
}