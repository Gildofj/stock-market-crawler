resource "google_service_account" "worker_sa" {
  account_id   = "crawler-worker-sa"
  display_name = "Service Account for Crawler Worker VM"
}

resource "google_compute_instance" "worker" {
  name         = "crawler-worker-vm"
  machine_type = "e2-micro"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    gce-container-declaration = yamlencode({
      spec = {
        containers = [{
          name  = "celery-worker"
          image = var.image_name
          env = [
            { name = "DATABASE_URL", value = var.database_url },
            { name = "REDIS_URL", value = var.redis_url },
            { name = "PYTHONPATH", value = "/app" }
          ]
          # The image will be updated by GitHub Actions during deploy
          args = ["celery", "-A", "crawler.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
        }]
        restartPolicy = "Always"
      }
    })
    google-logging-enabled = "true"
  }

  labels = {
    container-vm = "cos-stable"
  }

  service_account {
    email  = google_service_account.worker_sa.email
    scopes = ["cloud-platform"]
  }

  depends_on = [google_project_service.compute]
}

# Firewall rule to allow SSH (optional, for debugging)
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-crawler"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"] # Narrow this down to your IP in production
  target_tags   = ["ssh-enabled"]
}
