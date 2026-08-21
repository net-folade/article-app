terraform {
  # Terraform 1.10+ uses an S3 lock file instead of DynamoDB.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Backend settings cannot use variables. Each environment has its own key.
  backend "s3" {
    bucket       = "terraform-state-145b8d8b"
    key          = "envs/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

# Modules inherit this provider.
provider "aws" {
  region = var.region
}
