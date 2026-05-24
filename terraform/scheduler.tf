# Generic SA for HTTP-style Cloud Scheduler → Cloud Run (API) jobs.
# RI is scheduled separately as a Cloud Run Job (see cloud_run_job.tf);
# daily enqueue runs from the daily-sync.yml GitHub Action.

resource "google_project_service" "cloudscheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "scheduler_sa" {
  account_id   = "lagoai-scheduler"
  display_name = "Service Account for Cloud Scheduler → Cloud Run (API) calls"
}

# Defence-in-depth: API is allUsers today, but explicit run.invoker keeps the
# door open to lock it down later without breaking schedulers.
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}
