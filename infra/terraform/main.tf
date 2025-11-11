terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "3.0.2"
    }
  }
}

provider "docker" {}

resource "docker_image" "monitoring" {
  name         = "${var.dockerhub_username}/infra-monitoring-system:latest"
  keep_locally = false
}

resource "docker_container" "monitoring" {
  name  = "monitoring-app"
  image = docker_image.monitoring.name
  ports {
    internal = 8000
    external = 8000
  }
  env = [
    # Adicione variáveis de ambiente conforme necessário
  ]
}

resource "docker_image" "monitoring_metrics" {
  name         = "${var.dockerhub_username}/infra-monitoring-system_metrics:latest"
  keep_locally = false
}

resource "docker_container" "monitoring_metrics" {
  name  = "monitoring-metrics"
  image = docker_image.monitoring_metrics.name
  ports {
    internal = 8000
    external = 8000
  }
  env = [
    "MONITORING_HTTP_PORT=8000",
  "LOKI_URL=http://loki:3100/loki/api/v1/push",
    "LOKI_LABELS=job=infra-monitoring-system"
  ]
}

variable "dockerhub_username" {
  description = "Docker Hub username"
  type        = string
}
