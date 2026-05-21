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
          # GCE container declarations have no secret_key_ref; the entrypoint
          # shim (scripts/worker_entrypoint.sh) fetches secrets via the
          # metadata server using this VM's SA.
          env = [
            { name = "REDIS_HOST", value = "localhost" },
            { name = "PYTHONPATH", value = "/app" },
            { name = "GCP_PROJECT", value = var.project_id },
            { name = "R2_BUCKET_RI_DOCS", value = var.r2_bucket_ri_docs },
            { name = "R2_BUCKET_PORTFOLIOS", value = var.r2_bucket_portfolios },
            { name = "R2_RI_PUBLIC_BASE_URL", value = var.r2_ri_public_base_url },
          ]
          ports   = [{ containerPort = 6379, hostPort = 6379 }]
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

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-crawler"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"] # TODO: narrow to operator IP
  target_tags   = ["ssh-enabled"]
}

# Open Redis to the internet (password-protected) so the Cloud Run API can
# reach the cache/limiter.
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
