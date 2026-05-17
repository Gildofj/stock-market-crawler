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

output "ri_crawl_job" {
  description = "Cloud Run Job name + Scheduler trigger for the daily RI crawl."
  value = {
    job_name = google_cloud_run_v2_job.ri_crawl.name
    trigger  = google_cloud_scheduler_job.ri_crawl_trigger.name
  }
}
