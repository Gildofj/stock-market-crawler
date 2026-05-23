# Bootstrap-then-decouple: app_bootstrap seeds version 1 from tfvars on first
# apply; `ignore_changes = [secret_data]` then releases TF's grip so rotations
# happen via `gcloud secrets versions add <name> --data-file=-`.

locals {
  app_secrets = {
    "database-url"       = var.database_url
    "redis-password"     = var.redis_password
    "api-key"            = var.api_key
    "r2-account-id"      = var.r2_account_id
    "r2-api-token"       = var.r2_api_token
    "webshare-proxy-url" = var.webshare_proxy_url
  }
}

resource "google_secret_manager_secret" "app" {
  for_each  = local.app_secrets
  secret_id = each.key

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "app_bootstrap" {
  for_each    = local.app_secrets
  secret      = google_secret_manager_secret.app[each.key].id
  secret_data = each.value

  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

locals {
  secret_consumers = {
    api_runtime = google_service_account.api_runtime_sa.email
    ri_job      = google_service_account.ri_job_sa.email
  }

  secret_iam_bindings = {
    for pair in setproduct(keys(local.app_secrets), keys(local.secret_consumers)) :
    "${pair[0]}__${pair[1]}" => {
      secret_id = pair[0]
      sa_email  = local.secret_consumers[pair[1]]
    }
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each  = local.secret_iam_bindings
  secret_id = google_secret_manager_secret.app[each.value.secret_id].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa_email}"
}
