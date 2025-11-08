# Infra Monitoring System


[![CI]()
[![Codecov Coverage]()
[![Docker Build]()
[![Terraform Example]()
[![Docker Compose Ready]()
[![License MIT]()]

### Overview
Application developed for real-time system usage metrics collection and exposure, aiming to consolidate automation, continuous integration, and observability practices.
The codebase is built in **Python**, enabling measurement of CPU, memory, and processes, as well as structured export for integration with monitoring tools.
The project is **didactic** in nature, serving as a controlled environment for validation of pipelines, infrastructure as code, and container orchestration.

### Architecture and Flow
1. **Continuous Integration (CI):**
   Automatic syntax tests and dependency validation.
   Each commit triggers pipelines to ensure code consistency before build.

2. **Continuous Delivery (CD):**
   Automated packaging in Docker container.
   Controlled deploy with image versioning and post-deploy verification.

3. **Automated Infrastructure (IaC):**
   Environment definition and provisioning via **Terraform**, ensuring reproducibility and infrastructure isolation.

4. **Observability:**
   Application and environment metrics export via configurable endpoint.
   Integrated collection and visualization with **Prometheus** and **Grafana**, enabling performance analysis and operational alerts.

5. **Containerization:**
   Use of **Docker Compose** to orchestrate multiple system containers, simplifying initialization and local testing.

### Execution
```bash
# Clone the repository
git clone <repo-url>

# Build and run containers
docker-compose up --build

# Access local metrics
http://localhost:8000/metrics
```

### Environment and Tools
- **Language:** Python
- **Monitoring:** Prometheus, Grafana
- **Orchestration:** Docker, Docker Compose
- **Infrastructure:** Terraform
- **Pipeline:** GitHub Actions (CI/CD)
- **Operating System:** Linux (WSL compatible)

### Technical Note
The code was developed with a focus on learning and practical validation of automation, integration, and scalable infrastructure concepts.
The main application serves as a functional base for experimentation with real deployment and monitoring flows in a controlled environment.
