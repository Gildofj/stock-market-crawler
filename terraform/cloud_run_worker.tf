resource "google_cloud_run_v2_service" "worker" {
  name     = "stock-market-worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.api_runtime_sa.email

    containers {
      image = var.image_name
      ports {
        container_port = 8000
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
        name  = "ENV"
        value = "production"
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["api-key"].secret_id
            version = "latest"
          }
        }
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
        name  = "R2_BUCKET_PORTFOLIOS"
        value = var.r2_bucket_portfolios
      }
      env {
        name  = "R2_RI_PUBLIC_BASE_URL"
        value = var.r2_ri_public_base_url
      }
      env {
        name = "CRAWLER_HTTP_PROXY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["webshare-proxy-url"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "CRAWLER_HTTPS_PROXY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.app["webshare-proxy-url"].secret_id
            version = "latest"
          }
        }
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
    timeout = "900s"
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.cloudrun,
    google_secret_manager_secret_version.app_bootstrap,
    google_secret_manager_secret_iam_member.accessor,
  ]
}
