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
      image = "debian-cloud/debian-12"
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

  metadata_startup_script = <<-EOT
    #!/bin/bash
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker

    # Log in to Artifact Registry if needed (requires SA permissions)
    # gcloud auth configure-docker ${var.region}-docker.pkg.dev

    # Run the worker container
    sudo docker run -d \
      --name celery-worker \
      --restart always \
      -e DATABASE_URL="${var.database_url}" \
      -e REDIS_URL="${var.redis_url}" \
      -e PYTHONPATH=/app \
      "${var.image_name}" \
      celery -A crawler.celery_app worker --loglevel=info --concurrency=2
  EOT

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
