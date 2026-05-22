# Mars Rover Simulation Contract v0.1

## Verdict

`contract_only_mars_rover_sim`

This contract defines the Phase 1 Mars Rover simulation request schema for
TaijiOS SpaceOps Lab. It is simulation-only and learning-only.

It does not drive a real rover, robot, vehicle, drone, satellite, radio,
ground station, broker, exchange, or trading system.

## Parent Contract

```text
docs/TAIJIOS_SPACEOPS_LAB_v0.1.md
```

## Required Mission Request Fields

Every Mars Rover simulation mission request must contain:

- `mission_id`
- `target`
- `energy_budget`
- `terrain_risk`
- `comm_delay`
- `sensor_status`
- `allowed_actions`
- `forbidden_actions`
- `expected_closeout`

## Mission Request Schema

```json
{
  "mission_id": "string_non_empty",
  "target": {
    "site": "string_non_empty",
    "objective": "string_non_empty",
    "coordinates": {
      "lat": "number",
      "lon": "number"
    }
  },
  "energy_budget": {
    "unit": "Wh",
    "available": "number_positive",
    "reserve_minimum": "number_non_negative"
  },
  "terrain_risk": {
    "level": "low|medium|high",
    "hazards": ["string"]
  },
  "comm_delay": {
    "unit": "minutes",
    "one_way": "number_non_negative"
  },
  "sensor_status": {
    "navcam": "ok|degraded|failed",
    "hazcam": "ok|degraded|failed",
    "imu": "ok|degraded|failed",
    "wheel_odometry": "ok|degraded|failed"
  },
  "allowed_actions": ["simulate_path", "simulate_scan", "simulate_pause"],
  "forbidden_actions": [
    "real_vehicle_control",
    "satellite_command",
    "radio_tx",
    "external_api_call",
    "secret_read",
    "broker_connect",
    "trade",
    "paper_buy",
    "promote",
    "judge"
  ],
  "expected_closeout": {
    "boot_preflight_required": true,
    "event_flow_required": true,
    "closeout_required": true,
    "allowed_verdicts": ["success", "partial", "blocked"],
    "partial_blocked_cannot_be_success": true
  }
}
```

## Required Boundary Flags

The mission request or parent SpaceOps contract must preserve:

- `simulation_only=true`
- `learning_only=true`
- `no_real_vehicle_control=true`
- `no_satellite_command=true`
- `no_radio_tx=true`
- `no_external_api_by_default=true`
- `no_secret_access=true`
- `no_broker=true`
- `no_trade=true`
- `no_paper_buy=true`
- `no_promotion=true`
- `no_judgment=true`
- `boot_preflight_required=true`
- `event_flow_required=true`
- `closeout_required=true`
- `partial_blocked_cannot_be_success=true`
- `xuan_shu_is_renderer_only=true`

## Status Rules

- `success` requires boot preflight, parseable event flow, and closeout.
- `partial` is allowed only as a non-success verdict.
- `blocked` is allowed only as a non-success verdict.
- `partial` and `blocked` cannot be written as `success`.
- `degraded` sensor state can only lead to simulation analysis, `partial`, or
  `blocked`; it cannot become judgment, trade, paper-buy, or promotion.

## Forbidden Runtime Actions

This contract forbids:

- Starting, steering, moving, braking, or commanding a real rover or vehicle.
- Satellite command, radio transmission, or ground station command.
- External provider calls by default.
- Reading secrets or `.env` values.
- Broker, exchange, trade, paper-buy, promotion, judgment, or pass-to-trade
  behavior.
- Treating XuanShu renderer output as command authority.

## Expected Event Flow Minimum

Any future simulation runner must emit parseable JSONL events with at least:

```json
{
  "event": "mission_closeout",
  "mission_id": "MARS-SIM-EXAMPLE-001",
  "status": "partial",
  "simulation_only": true,
  "learning_only": true,
  "boot_preflight_passed": true,
  "external_api_called": false,
  "secret_accessed": false,
  "real_vehicle_control": false,
  "satellite_command": false,
  "radio_tx": false,
  "broker_connected": false,
  "trade_or_order": false,
  "judgment": false,
  "promotion": false,
  "wrote_closeout": true
}
```

The event flow example above is a schema example only, not evidence of a real
mission run.
