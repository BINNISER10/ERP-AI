.PHONY: build up down logs test validate clean build-flutter validate-local deploy-local deploy-prod backup help

# Default target: verify and build the whole stack.
all: validate build

## Show available targets
help:
	@echo "Nexus ERP — common tasks"
	@echo "  make build              Build all Docker images"
	@echo "  make up                 Start all services"
	@echo "  make down               Stop all services"
	@echo "  make logs               View logs"
	@echo "  make test               Run all tests (Python + Flutter)"
	@echo "  make validate           Run internal validate.py"
	@echo "  make validate-local     Run pre-deployment local checks"
	@echo "  make deploy-local       Start the local docker compose stack"
	@echo "  make deploy-prod        Deploy to production server"
	@echo "  make backup             Backup production databases"
	@echo "  make clean              Remove generated artifacts"

# Build all Docker images.
build:
	docker compose build

# Build Flutter Drift code generation.
build-flutter:
	cd flutter_pos && flutter pub get
	cd flutter_pos && dart run build_runner build --delete-conflicting-outputs

# Start all services.
up:
	docker compose up -d

# Stop all services.
down:
	docker compose down

# View logs.
logs:
	docker compose logs -f

# Run all tests.
test: test-python test-flutter

# Run Python tests.
test-python:
	cd ai_services && python -m pytest tests/ -q

# Run Flutter tests.
test-flutter:
	cd flutter_pos && flutter test

# Run the internal validation loop.
validate:
	python validate.py

# Run pre-deployment local checks.
validate-local:
	bash scripts/validate-local.sh

# Start local stack.
deploy-local: up

# Deploy to production server.
deploy-prod:
	bash scripts/deploy.sh

# Backup production databases.
backup:
	bash -c 'SERVER_IP=$$(powershell -ExecutionPolicy Bypass -File scripts/get-server-ip.ps1 2>/dev/null | tail -1); ssh -i terraform/oci_ssh_key.pem ubuntu@$$SERVER_IP "cd /opt/nexus-engine && ./scripts/backup.sh"'

# Clean generated artifacts.
clean:
	docker compose down -v
	rm -rf flutter_pos/build flutter_pos/.dart_tool flutter_pos/pubspec.lock
	rm -rf flutter_pos/lib/core/database/*.g.dart
	rm -rf flutter_pos/lib/core/database/tables.g.dart
