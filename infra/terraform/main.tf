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
  name         = "${var.dockerhub_username}/monitoring:latest"
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

variable "dockerhub_username" {
  description = "Docker Hub username"
  type        = string
}
