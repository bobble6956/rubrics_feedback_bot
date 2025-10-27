output "project_id" {
  value       = var.gcp_project_id
  description = "GCP Project ID"
}

output "service_account_email" {
  value       = google_service_account.app_sa.email
  description = "The email of the new service account."
}

#output "data_store_id" {
#  value       = google_discovery_engine_data_store.rubrics_datastore.data_store_id
#  description = "The ID of the Vertex AI Data Store."
#}

output "region" {
  value       = var.gcp_region
  description = "The primary region for Cloud Run."
}

#output "data_store_location" {
#  value       = var.data_store_location
#  description = "The location of the data store (e.g., global)."
#}

output "vertex_ai_location" {
  value       = var.vertex_ai_location
  description = "The location for Vertex AI API calls."
}