output "image_name" {
  description = "Full Docker image name used by the conceptual Terraform example"
  value       = docker_image.infra_monitoring.name
}

output "main_http_url" {
  description = "Convenience URL for the exporter endpoint (if applied)"
  value       = "http://localhost:${var.main_http_external_port}"
}
