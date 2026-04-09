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


def read_window_layout() -> dict | None:
    layout = addon_config().get(WINDOW_LAYOUT_CONFIG_KEY)
    return layout if isinstance(layout, dict) else None


def write_window_layout(layout: dict) -> None:
    config = addon_config()
    config[WINDOW_LAYOUT_CONFIG_KEY] = layout
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
