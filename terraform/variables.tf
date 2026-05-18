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
  description = "The Redis URL (previously Upstash, now pointing to GCE self-hosted)"
  type        = string
  sensitive   = true
}

variable "redis_password" {
  description = "Password for the self-hosted Redis instance on GCE"
  type        = string
  sensitive   = true
}

variable "allowed_origins" {
  description = "CORS allowed origins"
  type        = string
  default     = "*"
}

variable "api_key" {
  description = "Shared secret required on every API request (X-API-Key header). Rotated and re-injected by the GitHub Actions deploy workflow."
  type        = string
  sensitive   = true
}

variable "scheduler_timezone" {
  description = "IANA timezone used by Cloud Scheduler cron expressions."
  type        = string
  default     = "America/Sao_Paulo"
}

# Cloudflare R2 (S3-compatible) Object Storage — used for mirroring RI PDFs
# (public bucket) and storing portfolio spreadsheet uploads (private bucket).
# Leave the credentials blank to disable R2 integration; the application
# degrades gracefully and skips uploads when R2 is not configured.
variable "r2_account_id" {
  description = "Cloudflare account ID hosting the R2 buckets."
  type        = string
  default     = ""
  sensitive   = true
}

variable "r2_api_token" {
  description = "Cloudflare R2 API token (bearer). Used to derive S3 credentials in runtime."
  type        = string
  default     = ""
  sensitive   = true
}

variable "r2_bucket_ri_docs" {
  # LEGACY. RI PDFs are no longer mirrored — the upstream CVM URL is the
  # canonical reference. This variable is kept so existing tfvars / env stay
  # valid; the bucket can be drained manually when comfortable.
  description = "(Legacy) Former public mirror bucket for CVM RI PDFs. No longer written to."
  type        = string
  default     = "ri-docs"
}

variable "r2_bucket_portfolios" {
  description = "R2 bucket name for private portfolio spreadsheet uploads."
  type        = string
  default     = "portfolios"
}

variable "r2_ri_public_base_url" {
  # LEGACY. See `r2_bucket_ri_docs`. Kept to avoid breaking existing deploys.
  description = "(Legacy) Former public base URL for the RI mirror bucket."
  type        = string
  default     = ""
}
