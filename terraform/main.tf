resource "google_project_service" "apis" {
  for_each = toset([
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "cloudresourcemanager.googleapis.com"
  ])

  project = var.gcp_project_id
  service = each.key
}

resource "google_storage_bucket" "rubrics_bucket" {
  project                     = var.gcp_project_id
  name                        = var.rubrics_bucket_name
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  force_destroy               = true # Allows 'terraform destroy'

  depends_on = [
    google_project_service.apis
  ]
}

resource "google_storage_bucket_object" "rubrics_files" {
  for_each = fileset(var.rubrics_local_folder, "**/*.pdf")

  bucket = google_storage_bucket.rubrics_bucket.name
  name   = each.value
  source = "${var.rubrics_local_folder}/${each.value}"
}

resource "google_service_account" "app_sa" {
  project      = var.gcp_project_id
  account_id   = var.service_account_id
  display_name = "AI Rubrics Feedback Bot SA"
  depends_on = [
    google_project_service.apis
  ]
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/discoveryengine.viewer",
    "roles/storage.objectViewer",
    "roles/logging.logWriter"
  ])

  project = var.gcp_project_id
  role    = each.key
  member  = google_service_account.app_sa.member
}

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/iam.serviceAccountUser",
    "roles/cloudbuild.builds.builder"
  ])

  project = var.gcp_project_id
  role    = each.key
#  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"

  depends_on = [
    google_project_service.apis
  ]
}

data "google_project" "project" {
  project_id = var.gcp_project_id
}

#resource "google_discovery_engine_data_store" "rubrics_datastore" {
#  project           = var.gcp_project_id
#  location          = var.data_store_location
#  data_store_id     = "${var.cloud_run_service_name}-ds"
#  display_name      = "AI Rubrics Data Store"
#  industry_vertical = "GENERIC"
#  content_config    = "NO_CONTENT"
#  solution_types    = ["SOLUTION_TYPE_SEARCH"]
#  skip_default_schema_creation = true

#  depends_on = [
#    google_project_service.apis
#  ]
#}