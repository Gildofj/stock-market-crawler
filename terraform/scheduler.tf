# Cloud Scheduler API enable + a general-purpose service account for HTTP-style
# scheduled jobs targeting Cloud Run services. The LagoAI lake jobs that used
# to live here (news_collection / ri_collection) were removed:
#   * News runs from the Celery beat embedded in worker-hot (see celery_app.py).
#   * RI runs as a Cloud Run Job (see cloud_run_job.tf).
# Both previous schedulers pointed to /api/v1/internal/jobs/* endpoints that
# were never built, so removing them removes dead infra, not live traffic.

resource "google_project_service" "cloudscheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "scheduler_sa" {
  account_id   = "lagoai-scheduler"
  display_name = "Service Account for Cloud Scheduler → Cloud Run (API) calls"
}

# Defence-in-depth: even though the API allows allUsers today, granting
# run.invoker explicitly keeps the door open to lock the service down later
# by removing the noauth binding without breaking schedulers.
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}
