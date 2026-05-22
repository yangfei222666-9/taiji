# TaijiOS SpaceOps Lab v0.1

## Verdict

`contract_only_simulation_evidence_kernel`

TaijiOS SpaceOps Lab v0.1 defines a simulation-only Evidence Kernel lab line
for space exploration, robotics, delayed communications, and remote autonomy
mission planning. Phase 1 is a contract and schema layer only.

It does not control real vehicles, satellites, radios, robots, drones,
ground stations, brokers, or trading systems. It does not connect to external
providers by default and does not read secrets.

## Positioning

SpaceOps Lab is:

```text
simulation-only Evidence Kernel for remote autonomy missions
```

SpaceOps Lab is not a spacecraft control stack, rover driver, radio
transmitter, satellite command path, broker, execution engine, provider
adapter, judgment engine, or promotion lane.

## Contract Source

The Mars Rover simulation request contract for this phase is:

```text
docs/MARS_ROVER_SIM_CONTRACT_v0.1.md
```

The sample mission request is:

```text
examples/mars_rover_mission_request.json
```

The executable contract tests are:

```text
tests/test_spaceops_lab_contract.py
```

## Canonical Contract Object

```json
{
  "contract": "TAIJIOS_SPACEOPS_LAB",
  "contract_version": "0.1",
  "contract_phase": "contract_only",
  "mission_domain": "spaceops_remote_autonomy_simulation",
  "evidence_kernel_line": true,
  "simulation_only": true,
  "learning_only": true,
  "no_real_vehicle_control": true,
  "no_satellite_command": true,
  "no_radio_tx": true,
  "no_external_api_by_default": true,
  "no_secret_access": true,
  "no_broker": true,
  "no_trade": true,
  "no_paper_buy": true,
  "no_promotion": true,
  "no_judgment": true,
  "boot_preflight_required": true,
  "event_flow_required": true,
  "closeout_required": true,
  "partial_blocked_cannot_be_success": true,
  "xuan_shu_is_renderer_only": true
}
```

## Required True Flags

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

## Mission Lifecycle

Every SpaceOps Lab mission must start with `boot_preflight`.

Every mission must write parseable `event_flow`.

Every mission must produce a `closeout`.

The closeout may report:

- `success`
- `partial`
- `blocked`

The closeout must not write `partial` or `blocked` as `success`.

## Forbidden Capability Boundary

SpaceOps Lab v0.1 forbids:

- Real vehicle, rover, robot, drone, actuator, or manipulator control.
- Satellite command, radio transmit, uplink, downlink control, or ground
  station command.
- External API calls by default.
- Secret access, `.env` value reads, key export, or credential handling.
- Broker, exchange, trading, order, paper-buy, promotion, judgment, or
  pass-to-trade behavior.
- Treating simulation output as operational authority for a real mission.
- Treating XuanShu renderer output as a command or verdict source.

## Renderer Boundary

XuanShu may render SpaceOps Lab evidence states only after the Evidence Kernel
or closeout supplies the state.

XuanShu must remain `renderer_only`. It may display `simulation_only`,
`learning_only`, `event_flow_required`, `closeout_required`, `PARTIAL`, and
`BLOCKED`, but it must not generate verdicts, command vehicles, command
satellites, transmit radio, call providers, read secrets, trade, promote, or
judge.

## Phase 1 Validation

Run:

```bash
pytest tests/test_spaceops_lab_contract.py -q
python3 -m json.tool examples/mars_rover_mission_request.json >/dev/null
git diff --check
git status --short
```

## Non-Claims

SpaceOps Lab v0.1 does not prove:

- Real mission readiness.
- Real rover, vehicle, satellite, or radio integration.
- Provider availability.
- Secret availability.
- Broker, trade, paper-buy, judgment, promotion, or pass-to-trade authority.
- Repo pass, branch pass, commit pass, push pass, PR pass, or merge pass.
