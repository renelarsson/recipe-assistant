# ===============================
# Recipe Assistant Makefile
# ===============================
# This Makefile automates common development and deployment tasks for the Recipe Assistant project.
#
# Key features:
#   - Build, start, stop, and manage Docker Compose services
#   - Ingest data, initialize DB, run tests, lint code, view logs
#   - Example usage: make up
#   - To execute: up → ingest → db-init → health → test.
#   - To run all main steps at once: make all

# Variables
COMPOSE=docker compose
APP_CONTAINER=app
POSTGRES_CONTAINER=postgres

# Tell make that the listed targets are commands not actual files 
.PHONY: all up down build restart logs shell app-shell db-shell ingest db-init health test lint dlt grafana applog default

# 'all' target: Run the main workflow steps in order (useful for fresh setup or CI)
all: up ingest db-init health test lint

# Build and start all services (Docker Compose)
up:
	$(COMPOSE) up --build -d


# Stop all running containers (but do not remove them)
stop:
	$(COMPOSE) stop

# Stop and remove all services, networks, and anonymous volumes
down:
	$(COMPOSE) down

# Build Docker images only
build:
	$(COMPOSE) build

# Restart app and grafana containers
restart:
	$(COMPOSE) restart $(APP_CONTAINER) grafana


# Show all container logs (real-time, follow with -f)
logs:
	$(COMPOSE) logs

# Open bash shell in app container
app-shell:
	$(COMPOSE) exec $(APP_CONTAINER) bash

# Open bash shell in postgres container
db-shell:
	$(COMPOSE) exec $(POSTGRES_CONTAINER) bash

# Ingest data into Elasticsearch (inside app container)/add --no-prefect if timed out 
ingest:
	$(COMPOSE) exec $(APP_CONTAINER) python -m recipe_assistant.ingest --no-prefect

# Initialize/reset the PostgreSQL database (inside app container)
# (creates tables: conversations, feedback)
db-init:
	$(COMPOSE) exec $(APP_CONTAINER) python -m recipe_assistant.db_prep

# Check API health endpoint
health:
	curl -f http://localhost:5000/health

# Run the DLT pipeline (analytics data)
dlt:
	python3 ingestion/dlt_pipeline.py

# Run test script (API check)
test:
	python3 test.py

# Lint Python code (requires flake8)
lint:
	flake8 recipe_assistant ingestion

# Show application logs (logs/app.log)
applog:
	cat logs/app.log

# Open Grafana dashboard in browser (Linux only)
grafana:
	xdg-open http://localhost:3000 || echo "Open http://localhost:3000 in your browser."

# Show help for all available targets
default:
	@echo "Available targets:"
	@echo "  all        - Run all main steps in order (up, ingest, db-init, health, test)"
	@echo "  up         - Build and start all services (Docker Compose)"
	@echo "  stop       - Stop all running containers (but do not remove them)"
	@echo "  down       - Stop and remove all services, networks, and anonymous volumes"
	@echo "  build      - Build Docker images only"
	@echo "  restart    - Restart app and grafana containers"
	@echo "  logs       - Show all container logs"
	@echo "  app-shell  - Open bash shell in app container"
	@echo "  db-shell   - Open bash shell in postgres container"
	@echo "  ingest     - Ingest data into Elasticsearch (inside app container)"
	@echo "  db-init    - Initialize/reset the PostgreSQL database (inside app container)"
	@echo "  health     - Check API health endpoint"
	@echo "  dlt        - Run DLT pipeline (analytics data)"
	@echo "  test       - Run test script (API check)"
	@echo "  lint       - Lint Python code with flake8"
	@echo "  applog     - Show application logs (logs/app.log)"
	@echo "  grafana    - Open Grafana dashboard in browser"
