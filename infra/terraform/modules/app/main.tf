terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "3.0.2"
    }
  }
}

variable "name" {
  description = "Container name"
  type        = string
}

variable "image" {
  description = "Docker image name"
  type        = string
}

variable "command" {
  description = "Container command"
  type        = list(string)
}

variable "env" {
  description = "Environment variables"
  type        = list(string)
  default     = []
}

variable "volume_mounts" {
  description = "Host volume mounts"
  type = list(object({
    host_path      = string
    container_path = string
    read_only      = bool
  }))
  default = []
}

resource "docker_container" "this" {
  name    = var.name
  image   = var.image
  command = var.command

  env     = var.env
  restart = "unless-stopped"

  dynamic "volumes" {
    for_each = var.volume_mounts
    content {
      host_path      = volumes.value.host_path
      container_path = volumes.value.container_path
      read_only      = volumes.value.read_only
    }
  }
}

output "id" {
  value = docker_container.this.id
}
