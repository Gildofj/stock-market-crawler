resource "google_project_service" "cloudscheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "scheduler_sa" {
  account_id   = "lagoai-scheduler"
  display_name = "Service Account for LagoAI Cloud Scheduler"
}

# Grant the scheduler SA permission to invoke the Cloud Run API (defence-in-depth
# even though the service is currently public — keeps the door open to lock it
# down later by removing the `noauth` allUsers binding).
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_sa.email}"
}

# News collection — hourly. CVM IPE / RSS feeds tolerate this cadence well and
# Cloud Scheduler stays within the 3-jobs free quota.
resource "google_cloud_scheduler_job" "news_collection" {
  count       = var.enable_lagoai_scheduling ? 1 : 0
  name        = "lagoai-news-collection"
  description = "Triggers LagoAI news RSS collection."
  schedule    = "0 * * * *"
  time_zone   = var.scheduler_timezone
  region      = var.region

  attempt_deadline = "320s"
  retry_config {
    retry_count          = 1
    min_backoff_duration = "30s"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/v1/internal/jobs/news"
    headers = {
      "X-API-Key"    = var.api_key
      "Content-Type" = "application/json"
    }
    body = base64encode("{}")

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
      audience              = google_cloud_run_v2_service.api.uri
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}

# CVM RI documents — daily at 07:00 BRT (covers ITR / DFP / IPE).
resource "google_cloud_scheduler_job" "ri_collection" {
  count       = var.enable_lagoai_scheduling ? 1 : 0
  name        = "lagoai-ri-collection"
  description = "Triggers LagoAI CVM RI document collection."
  schedule    = "0 7 * * *"
  time_zone   = var.scheduler_timezone
  region      = var.region

  attempt_deadline = "320s"
  retry_config {
    retry_count          = 1
    min_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.api.uri}/api/v1/internal/jobs/ri"
    headers = {
      "X-API-Key"    = var.api_key
      "Content-Type" = "application/json"
    }
    body = base64encode("{}")

    oidc_token {
      service_account_email = google_service_account.scheduler_sa.email
      audience              = google_cloud_run_v2_service.api.uri
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}
