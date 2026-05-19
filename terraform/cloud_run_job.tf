# Cloud Run Job dedicated to the CVM RI document crawl.
#
# Why a Job instead of a Celery task on the worker VM:
#   * RI parses PDFs with pdfplumber, which spikes RAM hard. Running it on the
#     1 GB e2-micro means a single bad filing can OOM the whole VM and take
#     down the ticker / news crawls with it.
#   * RI runs only once a day, so paying for a Job (free tier: 240k vCPU-s/mo)
#     is dramatically under quota — ~9k vCPU-s/month at 1 vCPU × 5 min × 30 d.
#   * Independent release cadence: updating the RI spider doesn't reboot the
#     hot worker.
#
# The Job uses the SAME container image as the API and the workers, just with
# a different entrypoint (`python -m crawler.tasks.lake_ri`) — see
# crawler/tasks/lake_ri.py:main(). No second Dockerfile, no image divergence.

resource "google_service_account" "ri_job_sa" {
  account_id   = "lagoai-ri-job"
  display_name = "Service Account for LagoAI Cloud Run Job (RI crawl)"
}

# Allow the worker VM SA's image registry to be pulled by this Job.
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
    # Single execution, no parallelism — RI is a one-shot crawl.
    parallelism = 1
    task_count  = 1

    template {
      service_account = google_service_account.ri_job_sa.email
      # 30-minute ceiling matches the Celery soft_time_limit historically used
      # for this task (see crawler/tasks/lake_ri.py).
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
        # REDIS_URL is intentionally absent — the Job writes directly to
        # Postgres and never enqueues anything, so it has no business
        # holding a Redis connection.
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

        resources {
          limits = {
            cpu = "1"
            # pdfplumber is RAM-hungry; 1 GiB gives plenty of headroom and
            # the Job's instance-based GiB-seconds easily fits the 450k/mo
            # free quota at this cadence.
            memory = "1Gi"
          }
        }
      }
    }
  }

  # The deploy workflow rotates the image tag via `gcloud run jobs update`.
  # Ignore that drift so terraform apply doesn't roll back a fresh deploy.
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

# Cloud Scheduler invokes the Job via the Cloud Run Admin API. Free tier of
# Cloud Scheduler is 3 jobs/month; this brings the project to 1 active job
# (news/RI HTTP schedulers in scheduler.tf are flag-gated and disabled by
# default — see enable_lagoai_scheduling in variables.tf).
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
