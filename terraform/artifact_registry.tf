resource "google_artifact_registry_repository" "crawler_images" {
  location      = var.region
  repository_id = var.ar_repo
  description   = "Docker images for stock-market-crawler"
  format        = "DOCKER"

  depends_on = [google_project_service.artifactregistry]
}

