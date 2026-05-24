# Weekly Cloud Run Job that refreshes the B3 ticker universe in the
# `companies` table (CNPJ, cd_cvm, asset_type). Same container image as the
# API/worker; different entrypoint (python -m crawler.tasks.refresh_universe).

resource "google_service_account" "refresh_universe_job_sa" {
  account_id   = "refresh-universe-job"
  display_name = "Service Account for B3-driven ticker universe refresh"
}

resource "google_artifact_registry_repository_iam_member" "refresh_universe_job_reader" {
  location   = google_artifact_registry_repository.crawler_images.location
  repository = google_artifact_registry_repository.crawler_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.refresh_universe_job_sa.email}"
}

resource "google_cloud_run_v2_job" "refresh_universe" {
  name     = "refresh-universe"
  location = var.region

  template {
    parallelism = 1
    task_count  = 1

    template {
      service_account = google_service_account.refresh_universe_job_sa.email
      # 15 min is well above the expected ~3-5 min runtime.
      timeout     = "900s"
      max_retries = 1

      containers {
        image   = var.image_name_stealth != "" ? var.image_name_stealth : var.image_name
        command = ["python"]
        args    = ["-m", "crawler.tasks.refresh_universe"]

        env {
          name  = "ENABLE_TIER2_STEALTH"
          value = "true"
        }

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app["database-url"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        env {
          name  = "DB_POOL_SIZE"
          value = tostring(var.db_pool_size)
        }
        env {
          name  = "DB_MAX_OVERFLOW"
          value = tostring(var.db_max_overflow)
        }
        env {
          name  = "DB_STATEMENT_TIMEOUT_MS"
          value = tostring(var.db_statement_timeout_ms)
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.cloudrun,
    google_secret_manager_secret_version.app_bootstrap,
    google_secret_manager_secret_iam_member.accessor,
  ]
}

resource "google_service_account" "refresh_universe_invoker" {
  account_id   = "refresh-universe-invoker"
  display_name = "Cloud Scheduler invoker for refresh_universe Job"
}

resource "google_cloud_run_v2_job_iam_member" "refresh_universe_run_invoker" {
  project  = google_cloud_run_v2_job.refresh_universe.project
  location = google_cloud_run_v2_job.refresh_universe.location
  name     = google_cloud_run_v2_job.refresh_universe.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.refresh_universe_invoker.email}"
}

resource "google_cloud_scheduler_job" "refresh_universe_trigger" {
  name        = "refresh-universe-trigger"
  description = "Weekly B3-driven refresh of the ticker universe (Sun 03:00 BRT)."
  schedule    = "0 3 * * 0"
  time_zone   = var.scheduler_timezone
  region      = var.region

  attempt_deadline = "320s"
  retry_config {
    retry_count          = 1
    min_backoff_duration = "60s"
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.refresh_universe.name}:run"

    oauth_token {
      service_account_email = google_service_account.refresh_universe_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.cloudscheduler,
    google_cloud_run_v2_job_iam_member.refresh_universe_run_invoker,
  ]
}
