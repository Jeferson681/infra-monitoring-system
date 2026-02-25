provider "docker" {}

locals {
  image_name = "${var.dockerhub_username}/${var.image_repo}:${var.image_tag}"
}

# Conceptual image reference: the same repo image is used by both containers,
# matching docker/docker-compose.yml.
resource "docker_image" "infra_monitoring" {
  name         = local.image_name
  keep_locally = false
}

module "app" {
  source = "./modules/app"

  name          = var.app_container_name
  image         = docker_image.infra_monitoring.name
  command       = var.app_command
  env           = var.app_env
  volume_mounts = var.app_volume_mounts
}

module "main_http" {
  source = "./modules/main_http"

  name          = var.main_http_container_name
  image         = docker_image.infra_monitoring.name
  command       = var.main_http_command
  env           = var.main_http_env
  internal_port = var.main_http_internal_port
  external_port = var.main_http_external_port
  volume_mounts = var.main_http_volume_mounts

  depends_on = [module.app]
}
