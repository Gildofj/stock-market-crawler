resource "google_cloud_tasks_queue" "crawler_queue" {
  name     = "crawler-queue"
  location = var.region

  rate_limits {
    # Aligned with worker DB pool capacity (DB_POOL_SIZE + DB_MAX_OVERFLOW = 15,
    # but two services share the Supabase free-tier ceiling).
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 10
  }

  retry_config {
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 4
    max_retry_duration = "3600s"
  }

  depends_on = [google_project_service.cloudtasks]
}

# Conceder permissão ao Cloud Run para enfileirar tasks
resource "google_project_iam_member" "cloud_run_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.api_runtime_sa.email}"
}

# Conceder permissão ao Cloud Run para invocar endpoints HTTP do próprio Cloud Run
resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.api_runtime_sa.email}"
}

# Cloud Tasks attaches an OIDC token signed by `cloud-run-api-sa` to each
# enqueued HTTP task (see CloudTasksService.enqueue_task). The caller — which
# is *also* cloud-run-api-sa, since the API runs under that SA — must hold
# `iam.serviceAccountUser` on the SA being impersonated. Without this, Cloud
# Tasks returns 403 "lacks iam.serviceAccounts.actAs" on every create_task.
resource "google_service_account_iam_member" "api_runtime_sa_actas_self" {
  service_account_id = google_service_account.api_runtime_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api_runtime_sa.email}"
}
