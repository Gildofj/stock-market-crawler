output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "worker_vm_ip" {
  value = google_compute_instance.worker.network_interface[0].access_config[0].nat_ip
}
