"""Dashboard plugin surface — thin adapter around Mag data and actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mag.coordination import coordinate
from mag.context_pack import build_context_pack, format_context_pack_text
from mag.nervous_system import build_glance
from mag.router import route
from mag.system_map import build_system_map
from models.multi_smoke import last_smoke


@dataclass(frozen=True)
class DashboardPlugin:
    """Importable host adapter for the dashboard prototype."""

    name: str = "mag-dashboard"
    schema: str = "mag_dashboard_plugin.v1"

    def manifest(self, *, base_url: str = "http://127.0.0.1:8765") -> dict[str, Any]:
        return {
            "schema": self.schema,
            "name": self.name,
            "base_url": base_url,
            "data_contract": [
                "system_map",
                "nervous",
                "context_pack",
                "smoke_latest",
            ],
            "action_contract": [
                "route_goal",
                "coordinate_goal",
            ],
            "view_contract": [
                "dashboard/static/index.html",
                "dashboard/static/app.js",
            ],
            "endpoints": {
                "context_pack": "/api/v1/context-pack",
                "route": "/api/v1/route",
                "coordinate": "/api/v1/coordinate",
                "system_map": "/api/v1/system-map",
                "nervous": "/api/v1/nervous",
                "stack": "/api/v1/stack",
                "overview": "/api/v1/overview",
                "smoke_latest": "/api/multi-smoke/latest",
            },
            "smoke": {
                "pytest": "tests/test_routing_smoke.py",
                "script": "scripts/routing_smoke.py",
            },
        }

    def snapshot(self, *, goal: str = "", write: bool = False) -> dict[str, Any]:
        pack = build_context_pack(goal=goal, max_brief=900, max_live=500)
        return {
            "plugin": self.manifest(),
            "system_map": self.system_map(goal=goal, write=write),
            "nervous": self.nervous(),
            "context_pack": {
                "pack": pack,
                "text": format_context_pack_text(pack),
            },
            "smoke_latest": self.smoke_latest(),
        }

    def system_map(self, *, goal: str = "", write: bool = False) -> dict[str, Any]:
        return build_system_map(goal=goal, write=write)

    def nervous(self) -> dict[str, Any]:
        return build_glance(write=False)

    def context_pack(self, *, goal: str = "") -> dict[str, Any]:
        pack = build_context_pack(goal=goal, max_brief=900, max_live=500)
        return {
            "pack": pack,
            "text": format_context_pack_text(pack),
        }

    def smoke_latest(self) -> dict[str, Any] | None:
        return last_smoke()

    def route_goal(self, goal: str, **kwargs: Any) -> dict[str, Any]:
        return route(
            goal,
            depth=kwargs.get("depth"),
            force_seat=kwargs.get("force_seat"),
            force_provider=kwargs.get("force_provider"),
            signals=kwargs.get("signals"),
        )

    def coordinate_goal(self, goal: str, **kwargs: Any) -> dict[str, Any]:
        return coordinate(
            goal,
            launch=bool(kwargs.get("launch", True)),
            force_provider=kwargs.get("force_provider"),
            force_seat=kwargs.get("force_seat"),
        )


def build_dashboard_plugin() -> DashboardPlugin:
    return DashboardPlugin()
