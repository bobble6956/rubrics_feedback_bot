terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.8.0" # As requested, compatible with v7.8.0
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}