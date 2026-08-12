.PHONY: build up down logs test validate clean build-flutter

# Default target: verify and build the whole stack.
all: validate build

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

# Clean generated artifacts.
clean:
	docker compose down -v
	rm -rf flutter_pos/build flutter_pos/.dart_tool flutter_pos/pubspec.lock
	rm -rf flutter_pos/lib/core/database/*.g.dart
	rm -rf flutter_pos/lib/core/database/tables.g.dart
