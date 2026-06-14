from __future__ import annotations

# Package marker for the `backend.api` namespace.
#
# Routers are aggregated in `backend.api.router:api_router` (mounted by
# `backend/main.py`). The options router specifically is mounted via
# `backend.equity.routes:equity_router` (it carries its own `/api/options`
# prefix). Do NOT re-mount routers here — doing so double-registers paths.
