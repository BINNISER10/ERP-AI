# Nexus Forecourt Bridge

Standalone service that runs on a small industrial PC/gateway physically
next to the RS-485 bus at the fuel station. It talks to the 11 Lanfeng
pumps (23 nozzles), buffers readings durably on local disk, and pushes
them to the Odoo `nexus_fuel_station` module over HTTP.

```
[Lanfeng pumps] --RS-485--> [this bridge] --local SQLite queue--> HTTP JSON --> [Odoo]
```

This is the field-side counterpart of `odoo-backend/custom_addons/nexus_fuel_station`
(`fuel.forecourt.device`, `fuel.reading.buffer`, `/nexus_fuel/forecourt/readings`).

## Why a local queue?

Per the Ocean Seven technical study, connectivity between the station
and the Odoo server can drop. This bridge never loses a transaction:
every reading is written to `data/forecourt_queue.sqlite3` **before**
being sent, and only deleted once Odoo confirms receipt (accepted or
already-seen-duplicate). If the network is down, readings simply pile
up locally and flush automatically once it's back — Odoo's own
`transaction_ref` uniqueness constraint makes re-sends safe.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

Edit `config.yaml`:
- `odoo.base_url` / `odoo.api_key` — from the `fuel.forecourt.device`
  record created in Odoo (Fuel Station > Forecourt Controllers).
- `serial.protocol` — leave as `simulator` until Phase 1 below is done.
- `nozzle_map` — maps the controller's own address strings to the
  `controller_address` field you set on each `fuel.pump.nozzle` in Odoo.

## Commissioning phases (matches the technical study, Section 13)

1. **Phase 1 — Field protocol capture.** Connect ONE pump to a test PC
   via a USB↔RS-485 converter, run `protocol: simulator` bridge logic
   is not involved here — use a raw serial terminal to capture the byte
   stream for a real fill-up, and confirm frame format (start/end
   markers, pump/nozzle ID encoding, volume/amount fields, checksum).
   Implement the findings in `bridge/protocol/lanfeng.py::poll()`
   (currently raises `NotImplementedError` on purpose).
2. **Phase 2 — Central controller wiring.** Once the Forecourt
   Controller aggregates all 11 pumps, point `serial.port` at it and
   switch `serial.protocol: lanfeng`. Bring nozzles online one at a
   time, confirming each `controller_address` against Odoo before
   moving to the next.
3. **Phase 3 — Odoo hookup.** Run this bridge, then check
   **Fuel Station > Forecourt Readings** in Odoo — pending/processed/
   error rows should reflect each dispensing event within seconds.

## Running

```bash
python run.py --config config.yaml
```

Run it as a Windows service / systemd unit for production so it
survives reboots (not included here — use `nssm` on Windows or a
`.service` file on Linux).

## Testing without hardware

The default `protocol: simulator` in `config.example.yaml` generates
synthetic transactions across the 23 configured nozzle addresses every
few seconds, so the full pipeline (queue → HTTP push → Odoo processing)
can be validated end-to-end before any RS-485 wiring exists.

## Tests

```bash
python -m pytest tests/
```
