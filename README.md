# Nexus Enterprise Engine & Global Flutter POS Architecture

A full-stack, multi-company ERP reference architecture built around:

- **Odoo 18** back-end custom modules
- **Flutter 3.x** offline-first POS engine
- **FastAPI** AI microservices
- **Docker Compose** orchestration

## Repository Layout

```
.
├── config/                     # Odoo and PostgreSQL tuned configs
├── docker-compose.yml          # PostgreSQL, Redis, Odoo, AI services
├── Makefile                    # One-step build / up / down / test / validate
├── validate.py                 # Structural and import validation loop
├── odoo-backend/custom_addons/ # Odoo 18 modules
├── flutter_pos/                # Flutter POS (offline-first Drift/SQLite)
└── ai_services/                # FastAPI microservices (Text-to-SQL, OCR)
```

## Quick Start

1. Copy `.env.example` to `.env` and fill in secrets.
2. Start the infrastructure:

```powershell
make up
```

3. Build the Flutter POS:

```powershell
cd flutter_pos
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter run -t lib/main.dart
```

4. For the **US Retail & Hospitality** build target:

```powershell
flutter run -t lib/main_us_pos.dart --dart-define=STRIPE_PUBLISHABLE_KEY=pk_test_...
```

## Odoo Modules

| Module | Purpose |
|--------|---------|
| `nexus_base_security` | Shared groups and access control |
| `nexus_fuel_station` | Tanks, pumps, shift reconciliation |
| `nexus_real_estate` | Property units and lease contracts |
| `nexus_contracting` | Percentage-of-completion cost sheets |
| `nexus_zatca_compliance` | ZATCA XML C14N + SHA-256 hashing |
| `nexus_us_tax_engine` | Multi-jurisdiction US sales tax rates |
| `nexus_api_gateway` | JSON-RPC gateway for Flutter POS |
| `nexus_restaurant_costing` | Recipe BOM, inventory consumption, COGS |

## Flutter POS

- **Offline-first**: Drift/SQLite catalog, cart and order queues with sync state flags.
- **Network**: `OdooJsonRpcClient` with automatic offline retry and `/nexus_pos/jsonrpc` custom gateway.
- **Hardware**: Stripe Terminal, Mada POS, ESC/POS thermal printers, KDS broadcast.
- **US POS target**: USD currency, dynamic US state sales tax, tip selection, split-bill logic, card reader integration.

## AI Services

- `/api/v1/sql/ask` — Text-to-SQL with read-only PostgreSQL access and strict mutation blocking.
- `/api/v1/ocr/invoice` — OCR + invoice field extraction.

## Validation

Run the internal validation loop:

```powershell
python validate.py
```

This checks Python syntax, relative imports, Odoo manifest data files, Flutter file references, and pubspec dependencies. If Flutter is installed, it also runs `build_runner` to generate Drift `.g.dart` files.
