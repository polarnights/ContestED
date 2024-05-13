locals {
  db_name = "tasks-db"
}

resource "yandex_ydb_database_serverless" "tasks_db" {
  name      = local.db_name
  folder_id = var.folder_id
}

output "tasks_db_document_api_endpoint" {
  value = yandex_ydb_database_serverless.tasks_db.document_api_endpoint
}

output "tasks_db_path" {
  value = yandex_ydb_database_serverless.tasks_db.database_path
}