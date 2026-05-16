resource "google_cloud_run_v2_service" "api" {
  name     = "stock-market-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.image_name
      ports {
        container_port = 8000
      }
      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "REDIS_URL"
        value = var.redis_url
      }
      env {
        name  = "ENV"
        value = "production"
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "API_KEY"
        value = var.api_key
      }
      env {
        name  = "R2_ACCOUNT_ID"
        value = var.r2_account_id
      }
      env {
        name  = "R2_API_TOKEN"
        value = var.r2_api_token
      }
      env {
        name  = "R2_BUCKET_RI_DOCS"
        value = var.r2_bucket_ri_docs
      }
      env {
        name  = "R2_BUCKET_PORTFOLIOS"
        value = var.r2_bucket_portfolios
      }
      env {
        name  = "R2_RI_PUBLIC_BASE_URL"
        value = var.r2_ri_public_base_url
      }
      resources {
        limits = {
          cpu = "1"
          # Bumped from 512Mi to handle pandas-based spreadsheet parsing in the
          # /carteira router and pdfplumber sidecars. Free tier (360k GiB-s/mo)
          # still covers ~100h of active time at 1 GiB.
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
    }
    scaling {
      max_instance_count = 3
      min_instance_count = 0
    }
    timeout = "60s"
  }

  # The deploy workflow (.github/workflows/deploy.yml) rotates the image tag
  # and may update env vars via `gcloud run deploy --update-env-vars`. Ignore
  # those drifts so that `terraform apply` does not roll back a fresh deploy.
  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[0].env,
    ]
  }

  depends_on = [google_project_service.cloudrun]
}

# Allow unauthenticated access (Cloudflare will handle proxying/security)
resource "google_cloud_run_service_iam_member" "noauth" {
  location = google_cloud_run_v2_service.api.location
  project  = google_cloud_run_v2_service.api.project
  service  = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
