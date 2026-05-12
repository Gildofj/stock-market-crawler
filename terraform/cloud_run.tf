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
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
    scaling {
      max_instance_count = 10
      min_instance_count = 0
    }
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
