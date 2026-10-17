# Dashboard plugin surface

The dashboard in `local_sovereign_agent` is the prototype control surface. Treat it as a host UI that can expose Mag data and actions through a stable contract instead of a one-off page.

## Smoke tests

The smoke pair lives here:

- `tests/test_routing_smoke.py` - pytest-visible wrapper for VS Code Test Explorer
- `scripts/routing_smoke.py` - executable routing contract

If the Testing pane is opened from the parent workspace (`c:\Users\ESTATE_USER\Documents\projects`), it needs workspace-level pytest settings that point at `local_sovereign_agent/tests`.

## Existing plugin-like surfaces

These are already the clean integration points for an imported plugin or dashboard module:

- `GET /api/v1/context-pack`
- `GET /api/v1/route`
- `POST /api/v1/coordinate`
- `GET /api/v1/system-map`
- `GET /api/v1/nervous`
- `GET /api/v1/stack`
- `GET /api/v1/overview`
- `GET /api/multi-smoke/latest`

The prototype UI already renders these as tabs and panels in `dashboard/static/index.html` and `dashboard/static/app.js`.

The importable adapter lives in `mag/dashboard_plugin.py`.

## Mapping idea

A future plugin should be a thin adapter around three things:

1. Data contract: system map, nervous glance, context pack, routing state, smoke state.
2. Action contract: route, coordinate, queue, drain, improve, and verify.
3. View contract: dashboard sections that render the data without duplicating the Mag core.

## Recommended shape

- Keep Mag logic in `mag/*` and `dashboard/rest.py`.
- Keep the UI thin and data-driven.
- Add new views by extending the REST contract first, then rendering them in the dashboard.
- If a separate plugin package is created later, have it import the same REST/data contract instead of reimplementing Mag behavior.

## Immediate note

The current smoke test is discoverable from the nested repo root, but the parent workspace needs its own `.vscode/settings.json` to make VS Code's Testing pane show `local_sovereign_agent/tests`.

The parent workspace also has a `pytest.ini` that points collection at `local_sovereign_agent/tests`.
