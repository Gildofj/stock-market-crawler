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

variable "image_name_stealth" {
  description = "The Docker image name for Tier 2 stealth tasks"
  type        = string
  default     = ""
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

variable "webshare_proxy_url" {
  description = "Proxy URL for Webshare to circumvent IP blocks"
  type        = string
  sensitive   = true
  default     = ""
}



# DB pool tuning — exposed as plain vars (not secrets) so they can be tweaked
# per environment without rebuilding the container image. Defaults match
# core/config.py for Supabase free tier behind Supavisor transaction pooler.
variable "db_pool_size" {
  description = "SQLAlchemy pool_size per service instance. Keep small when behind a connection pooler (Supavisor multiplexes)."
  type        = number
  default     = 5
}

variable "db_max_overflow" {
  description = "SQLAlchemy max_overflow — connections beyond pool_size allowed under burst."
  type        = number
  default     = 10
}

variable "db_statement_timeout_ms" {
  description = "Postgres statement_timeout in ms. Hard kill for runaway queries that would otherwise hold a pool slot indefinitely."
  type        = number
  default     = 30000
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

# Cloudflare R2 (S3-compatible). Leave credentials blank to disable; the app
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
  # LEGACY. RI PDFs are no longer mirrored (upstream CVM URL is canonical).
  # Kept so existing tfvars/env stay valid; bucket can be drained manually.
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
  # LEGACY — see r2_bucket_ri_docs.
  description = "(Legacy) Former public base URL for the RI mirror bucket."
  type        = string
  default     = ""
}

