from __future__ import annotations

try:
    from .addon import register
except ModuleNotFoundError:
    register = None
else:
    register()
