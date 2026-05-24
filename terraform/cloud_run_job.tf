# RI runs as a Cloud Run Job (not a Celery task) because pdfplumber's RAM
# spikes would OOM the 1 GB worker VM and take ticker/news down with it.
# Same container image, different entrypoint (python -m crawler.tasks.lake_ri).

resource "google_service_account" "ri_job_sa" {
  account_id   = "lagoai-ri-job"
  display_name = "Service Account for LagoAI Cloud Run Job (RI crawl)"
}

resource "google_artifact_registry_repository_iam_member" "ri_job_reader" {
  location   = google_artifact_registry_repository.crawler_images.location
  repository = google_artifact_registry_repository.crawler_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.ri_job_sa.email}"
}

resource "google_cloud_run_v2_job" "ri_crawl" {
  name     = "lagoai-ri-crawl"
  location = var.region

  template {
    parallelism = 1
    task_count  = 1

    template {
      service_account = google_service_account.ri_job_sa.email
      # 30 min matches the historical Celery soft_time_limit for this task.
      timeout     = "1800s"
      max_retries = 1

      containers {
        image   = var.image_name
        command = ["python"]
        args    = ["-m", "crawler.tasks.lake_ri"]

        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app["database-url"].secret_id
              version = "latest"
            }
          }
        }
        # REDIS_URL absent on purpose: the Job writes directly to Postgres.
        env {
          name  = "PYTHONPATH"
          value = "/app"
        }
        env {
          name  = "RI_DAYS_BACK"
          value = "7"
        }
        env {
          name = "R2_ACCOUNT_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app["r2-account-id"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "R2_API_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app["r2-api-token"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "R2_BUCKET_RI_DOCS"
          value = var.r2_bucket_ri_docs
        }
        env {
          name  = "R2_RI_PUBLIC_BASE_URL"
          value = var.r2_ri_public_base_url
        }
        env {
          name = "BRAPI_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app["brapi-token"].secret_id
              version = "latest"
            }
          }
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
            memory = "1Gi" # pdfplumber needs headroom; fits the 450k GiB-s/mo free quota.
          }
        }
      }
    }
  }

  # Deploy workflow rotates the image tag via `gcloud run jobs update`; ignore
  # that drift so terraform apply doesn't roll back a fresh deploy.
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

resource "google_service_account" "ri_job_invoker" {
  account_id   = "lagoai-ri-invoker"
  display_name = "Cloud Scheduler invoker for LagoAI RI Job"
}

resource "google_cloud_run_v2_job_iam_member" "ri_job_run_invoker" {
  project  = google_cloud_run_v2_job.ri_crawl.project
  location = google_cloud_run_v2_job.ri_crawl.location
  name     = google_cloud_run_v2_job.ri_crawl.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.ri_job_invoker.email}"
}

resource "google_cloud_scheduler_job" "ri_crawl_trigger" {
  name        = "lagoai-ri-crawl-trigger"
  description = "Daily trigger for the RI Cloud Run Job (07:00 BRT)."
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
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.ri_crawl.name}:run"

    oauth_token {
      service_account_email = google_service_account.ri_job_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.cloudscheduler,
    google_cloud_run_v2_job_iam_member.ri_job_run_invoker,
  ]
}
