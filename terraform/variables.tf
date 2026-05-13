variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for Cloud Run and VM (us-central1 is recommended for Free Tier)"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "image_name" {
  description = "The Docker image name (e.g., gcr.io/PROJECT_ID/stock-market-crawler)"
  type        = string
}

variable "ar_repo" {
  description = "Artifact Registry repository id for crawler images (must match AR_REPO GitHub Variable)"
  type        = string
  default     = "crawler-images"
}

variable "database_url" {
  description = "The Supabase database URL"
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "The Upstash Redis URL"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "CORS allowed origins"
  type        = string
  default     = "*"
}
