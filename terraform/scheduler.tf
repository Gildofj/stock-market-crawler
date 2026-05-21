# Generic SA for HTTP-style Cloud Scheduler → Cloud Run (API) jobs.
# Previous LagoAI lake schedulers were removed: news now runs from Celery beat
# (celery_app.py), RI as a Cloud Run Job (cloud_run_job.tf).

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
