variable "dockerhub_username" {
  description = "Docker Hub username (conceptual example: used to compose the image name)"
  type        = string
}

variable "image_repo" {
  description = "Docker image repository name (matches docker/docker-compose.yml build output)"
  type        = string
  default     = "infra-monitoring-system"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "app_container_name" {
  description = "Container name for the long-running app loop (docker-compose: infra-monitoring-system_app)"
  type        = string
  default     = "infra-monitoring-system_app"
}

variable "main_http_container_name" {
  description = "Container name for the HTTP exporter service (docker-compose: infra-monitoring-main-http)"
  type        = string
  default     = "infra-monitoring-main-http"
}

variable "app_command" {
  description = "Command used by the app container"
  type        = list(string)
  default     = ["python", "-m", "src.main"]
}

variable "main_http_command" {
  description = "Command used by the HTTP exporter container"
  type        = list(string)
  default     = ["python", "-u", "-m", "infra_monitoring.api.exporter.main_http"]
}

variable "app_env" {
  description = "Environment variables for the app container (kept aligned with docker/docker-compose.yml defaults)"
  type        = list(string)
  default = [
    "MONITORING_HTTP_ENABLE=0",
    "MONITORING_HTTP_PORT=8000",
    "MONITORING_PROMTAIL_ENABLE=1",
    "MONITORING_CYCLES=0",
  ]
}

variable "main_http_env" {
  description = "Environment variables for the main_http container (kept aligned with docker/docker-compose.yml defaults)"
  type        = list(string)
  default = [
    "MONITORING_HTTP_ADDR=0.0.0.0",
    "MONITORING_HTTP_PORT=8000",
  ]
}

variable "main_http_internal_port" {
  description = "Internal container port for the exporter"
  type        = number
  default     = 8000
}

variable "main_http_external_port" {
  description = "External host port for the exporter"
  type        = number
  default     = 8000
}

variable "app_volume_mounts" {
  description = "Conceptual host volume mounts for the app container. Keep empty by default for cross-platform validation."
  type = list(object({
    host_path      = string
    container_path = string
    read_only      = bool
  }))
  default = []
}

variable "main_http_volume_mounts" {
  description = "Conceptual host volume mounts for the main_http container. Keep empty by default for cross-platform validation."
  type = list(object({
    host_path      = string
    container_path = string
    read_only      = bool
  }))
  default = []
}
