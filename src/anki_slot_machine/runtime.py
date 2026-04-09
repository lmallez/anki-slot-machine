from __future__ import annotations

from pathlib import Path

from aqt import mw

ADDON_MODULE = __name__.split(".")[0]
WEB_EXPORT_PATTERN = r"web/.*(css|js|png)"
STATE_FILENAME = "slot_machine_state.json"
WINDOW_LAYOUT_CONFIG_KEY = "window_layout"


def addon_config() -> dict:
    return mw.addonManager.getConfig(ADDON_MODULE) or {}


def write_addon_config(config: dict) -> None:
    mw.addonManager.writeConfig(ADDON_MODULE, config)


def read_window_layouts() -> dict[str, dict]:
    layout = addon_config().get(WINDOW_LAYOUT_CONFIG_KEY)
    if not isinstance(layout, dict):
        return {}

    if any(key in layout for key in ("left", "top", "width", "height", "mode")):
        return {"main": layout}

    return {
        str(key): value
        for key, value in layout.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def read_window_layout(machine_key: str | None = None) -> dict | None:
    layouts = read_window_layouts()
    if machine_key is None:
        return layouts.get("main")
    return layouts.get(machine_key)


def write_window_layout(layout: dict, machine_key: str | None = None) -> None:
    config = addon_config()
    if machine_key is None:
        config[WINDOW_LAYOUT_CONFIG_KEY] = layout
    else:
        layouts = read_window_layouts()
        layouts[machine_key] = layout
        config[WINDOW_LAYOUT_CONFIG_KEY] = layouts
    write_addon_config(config)


def delete_window_layout(machine_key: str) -> None:
    config = addon_config()
    layouts = read_window_layouts()
    if machine_key not in layouts:
        return
    del layouts[machine_key]
    config[WINDOW_LAYOUT_CONFIG_KEY] = layouts
    write_addon_config(config)


def register_web_exports() -> None:
    mw.addonManager.setWebExports(ADDON_MODULE, WEB_EXPORT_PATTERN)


def addon_package_name() -> str:
    return mw.addonManager.addonFromModule(ADDON_MODULE)


def addon_instance_key() -> str:
    return addon_package_name()


def addon_root() -> Path:
    return Path(mw.addonManager.addonsFolder()) / addon_package_name()


def addon_user_files_dir() -> Path:
    path = addon_root() / "user_files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path() -> Path:
    return addon_user_files_dir() / STATE_FILENAME


def addon_web_base_url() -> str:
    register_web_exports()
    return f"/_addons/{addon_package_name()}/web"
