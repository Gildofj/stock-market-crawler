resource "google_service_account" "worker_sa" {
  account_id   = "crawler-worker-sa"
  display_name = "Service Account for Crawler Worker VM"
}

resource "google_compute_instance" "worker" {
  name         = "crawler-worker-vm"
  machine_type = "e2-micro"
  zone         = var.zone
  tags         = ["ssh-enabled", "redis-enabled"]

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
            # Points to the local Redis started by the entrypoint
            { name = "REDIS_URL", value = "redis://:${var.redis_password}@localhost:6379/0" },
            { name = "PYTHONPATH", value = "/app" },
            { name = "R2_ACCOUNT_ID", value = var.r2_account_id },
            { name = "R2_API_TOKEN", value = var.r2_api_token },
            { name = "R2_BUCKET_RI_DOCS", value = var.r2_bucket_ri_docs },
            { name = "R2_BUCKET_PORTFOLIOS", value = var.r2_bucket_portfolios },
            { name = "R2_RI_PUBLIC_BASE_URL", value = var.r2_ri_public_base_url },
          ]
          ports = [{ containerPort = 6379, hostPort = 6379 }]
          command = ["/app/scripts/worker_entrypoint.sh"]
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

# Firewall rule to allow Redis access from the internet (protected by password)
# Needed for the API running on Cloud Run to access the cache/limiter.
resource "google_compute_firewall" "allow_redis" {
  name    = "allow-redis-crawler"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["6379"]
  }

  source_ranges = ["0.0.0.0/0"] 
  target_tags   = ["redis-enabled"]
}
