# Terraform Examples — Educational / Demonstrative Use

This folder contains Terraform example files that demonstrate Infrastructure as Code (IaC) concepts in the context of this project.
These files can be used freely for study, local tests, or controlled provisioning of simple environments.

## Important notes

The examples are minimal and illustrative, focused on understanding blocks, variables, and provisioning flows.

Before applying to any real environment, review and adapt to your needs (networking, security, IAM policies, remote backend, etc.).

Remote state and concurrency locking are not configured by default.

### Local syntax validation

```sh
cd infra/terraform
terraform init -backend=false
terraform validate
```

### Safe execution in a test environment

```sh
terraform plan
terraform apply
```

Recommendation: use an isolated account or workspace to avoid unintended changes to critical environments.

---

For details on collection limits (`psutil`), persistence (JSONL), and exporter activation, see `docs/DECISIONS.md`. Run instructions and examples are in `docs/RUN.md`.

---
## Summary

Terraform usage in this project is fully optional.
It serves as a didactic base and can be adapted for real deployments, considering the differences between physical host metrics and metrics from the provisioned environment.
