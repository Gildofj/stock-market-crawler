output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "worker_vm_ip" {
  value = google_compute_instance.worker.network_interface[0].access_config[0].nat_ip
}

output "scheduler_service_account" {
  description = "Service account used by Cloud Scheduler to invoke Cloud Run."
  value       = google_service_account.scheduler_sa.email
}

output "scheduler_jobs" {
  description = "Cloud Scheduler job IDs for LagoAI lake collection (null if disabled)."
  value = var.enable_lagoai_scheduling ? {
    news = google_cloud_scheduler_job.news_collection[0].name
    ri   = google_cloud_scheduler_job.ri_collection[0].name
  } : null
}
