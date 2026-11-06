"""Smart Dashboard Switcher: a persistent Home Assistant panel."""
from pathlib import Path
import logging
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components import panel_custom, frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN, PANEL_URL, CONF_PANEL_URL, CONF_SHOW_SIDEBAR

_LOGGER = logging.getLogger(__name__)
RESOURCE_URL = "/smart_dashboard_switcher/switcher.js"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    cfg = {**entry.data, **entry.options}
    # Static routes persist across config-entry reloads. Register only once.
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("static_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                "/smart_dashboard_switcher/switcher.js",
                str(Path(__file__).parent / "frontend" / "switcher.js"),
                cache_headers=False,
            )
        ])
        domain_data["static_registered"] = True
    panel_url = cfg.get(CONF_PANEL_URL, PANEL_URL)
    show_sidebar = cfg.get(CONF_SHOW_SIDEBAR, True)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="smart-dashboard-switcher-panel",
        frontend_url_path=panel_url,
        module_url="/smart_dashboard_switcher/switcher.js",
        sidebar_title=("Info Display" if panel_url == PANEL_URL else f"Info Display ({panel_url})") if show_sidebar else None,
        sidebar_icon="mdi:tablet-dashboard" if show_sidebar else None,
        require_admin=False,
        config=cfg,
    )
    await _async_ensure_dashboard(hass, cfg)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    panel_url = entry.options.get(CONF_PANEL_URL, entry.data.get(CONF_PANEL_URL, PANEL_URL))
    frontend.async_remove_panel(hass, panel_url)
    return True


async def _async_ensure_dashboard(hass: HomeAssistant, cfg: dict) -> None:
    """Create/update only our own storage dashboard; never edit other dashboards."""
    panel_url = cfg.get(CONF_PANEL_URL, PANEL_URL)
    dashboard_url = f"dashboard-{panel_url}"
    title = "Info Display" if panel_url == PANEL_URL else f"Info Display ({panel_url})"
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        _LOGGER.error("Lovelace is not available; cannot create %s", dashboard_url)
        return

    # Ensure the custom card loads without requiring a manual Resources step.
    resources = lovelace.resources
    try:
        if hasattr(resources, "async_load") and not getattr(resources, "loaded", False):
            await resources.async_load()
        if hasattr(resources, "async_create_item"):
            if not any(item.get("url", "").split("?")[0] == RESOURCE_URL for item in resources.async_items()):
                await resources.async_create_item({"url": RESOURCE_URL, "res_type": "module"})
        else:
            _LOGGER.warning("Lovelace resources are YAML-managed; add %s manually", RESOURCE_URL)
    except Exception:
        _LOGGER.exception("Unable to register Lovelace resource %s", RESOURCE_URL)

    try:
        collection = lovelace_dashboard.DashboardsCollection(hass)
        await collection.async_load()
        existing = next((item for item in collection.async_items()
                         if item.get("url_path") == dashboard_url), None)
        if existing is None:
            # An unrelated panel could already use this URL. Never replace it.
            if frontend.async_panel_exists(hass, dashboard_url):
                _LOGGER.error("Dashboard URL %s is occupied", dashboard_url)
                return
            await collection.async_create_item({
                "url_path": dashboard_url, "title": title,
                "icon": "mdi:tablet-dashboard", "show_in_sidebar": False,
                "require_admin": False,
            })
            # This is a separate collection instance; Home Assistant's listener
            # is attached to its original instance. Register the new dashboard
            # for the current session as well as persisting it for next restart.
            item = next(item for item in collection.async_items()
                        if item.get("url_path") == dashboard_url)
            store = lovelace_dashboard.LovelaceStorage(hass, item)
            lovelace.dashboards[dashboard_url] = store
            # Hidden from the sidebar the same way Lovelace does it: no
            # sidebar title/icon. (show_in_sidebar= is not accepted by
            # every Home Assistant version.)
            frontend.async_register_built_in_panel(
                hass, "lovelace", frontend_url_path=dashboard_url,
                require_admin=False, config={"mode": "storage"},
            )
        else:
            store = lovelace.dashboards.get(dashboard_url)
            if store is None:
                _LOGGER.error("Dashboard %s exists but is not available", dashboard_url)
                return

        desired = {
            "title": title,
            "views": [{
                "title": title, "path": "0", "type": "panel",
                "cards": [{
                    "type": "custom:smart-dashboard-switcher-card",
                    "panel_url": panel_url,
                    "entity": cfg["entity"], "on_path": cfg["on_path"],
                    "off_path": cfg["off_path"],
                    "delay_on": cfg.get("delay_on", 30),
                    "delay_off": cfg.get("delay_off", 120),
                }],
            }],
        }
        if existing is None:
            await store.async_save(desired)
        else:
            current = await store.async_load(force=True)
            views = current.get("views", []) if isinstance(current, dict) else []
            cards = views[0].get("cards", []) if len(views) == 1 else []
            # Only update our unmodified, single-card dashboard. Do not
            # overwrite user-created or user-edited dashboard content.
            if (len(cards) == 1 and cards[0].get("type") ==
                    "custom:smart-dashboard-switcher-card" and
                    cards[0].get("panel_url") == panel_url):
                if current != desired:
                    await store.async_save(desired)
            else:
                _LOGGER.warning("Dashboard %s was customized; not overwriting", dashboard_url)
    except Exception:
        _LOGGER.exception("Could not create/update dashboard %s", dashboard_url)
