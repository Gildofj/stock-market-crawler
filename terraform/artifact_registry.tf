resource "google_artifact_registry_repository" "crawler_images" {
  location      = var.region
  repository_id = var.ar_repo
  description   = "Docker images for stock-market-crawler"
  format        = "DOCKER"

  depends_on = [google_project_service.artifactregistry]
}

# Allow the worker VM SA to pull images from the registry.
resource "google_artifact_registry_repository_iam_member" "worker_reader" {
  location   = google_artifact_registry_repository.crawler_images.location
  repository = google_artifact_registry_repository.crawler_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.worker_sa.email}"
}
