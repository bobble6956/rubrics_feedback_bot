variable "gcp_project_id" {
  type        = string
  description = "The GCP Project ID to deploy all resources into."
}

variable "gcp_region" {
  type        = string
  description = "The primary region for resources like Cloud Run and GCS."
  default     = "us-central1"
}

variable "vertex_ai_location" {
  type        = string
  description = "The location for Vertex AI API calls, as defined in your app.py."
  default     = "us-central1"
}

#variable "data_store_location" {
#  type        = string
#  description = "The location for the Discovery Engine Data Store. Per your README, this is 'global'."
#  default     = "global"
#}

variable "rubrics_bucket_name" {
  type        = string
  description = "A unique name for the GCS bucket to store rubric PDFs. Must be globally unique."
}

variable "service_account_id" {
  type        = string
  description = "The ID for the service account (e.g., 'essay-bot-sa')."
  default     = "essay-bot-sa"
}

variable "rubrics_local_folder" {
  type        = string
  description = "The local path to your 'rubrics' folder, relative to these .tf files."
  default     = "../rubrics" # Assumes a 'rubrics' folder in the same directory
}