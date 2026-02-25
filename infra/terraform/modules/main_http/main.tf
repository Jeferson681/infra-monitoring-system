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

variable "internal_port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "external_port" {
  description = "Host port"
  type        = number
  default     = 8000
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

  ports {
    internal = var.internal_port
    external = var.external_port
  }

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
