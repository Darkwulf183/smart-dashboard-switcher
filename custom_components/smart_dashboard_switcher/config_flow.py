"""Configuration flow for Smart Dashboard Switcher."""
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CONF_ENTITY, CONF_ON_PATH, CONF_OFF_PATH, CONF_SHOW_SIDEBAR,
    CONF_DELAY_ON, CONF_DELAY_OFF, DEFAULT_DELAY_ON, DEFAULT_DELAY_OFF, CONF_PANEL_URL, PANEL_URL,
)


def _schema(data, panel_default=PANEL_URL):
    return vol.Schema({
        vol.Required(CONF_SHOW_SIDEBAR, default=data.get(CONF_SHOW_SIDEBAR, True)): selector.BooleanSelector(),
        vol.Required(CONF_PANEL_URL, default=data.get(CONF_PANEL_URL, panel_default)): selector.TextSelector(),
        # Only pre-fill an entity the user already chose; others won't have ours.
        (vol.Required(CONF_ENTITY, default=data[CONF_ENTITY]) if data.get(CONF_ENTITY)
         else vol.Required(CONF_ENTITY)):
            selector.EntitySelector(selector.EntitySelectorConfig(domain=["switch", "binary_sensor", "input_boolean"])),
        vol.Required(CONF_ON_PATH, default=data.get(CONF_ON_PATH, "/heizung/0")): selector.TextSelector(),
        vol.Required(CONF_OFF_PATH, default=data.get(CONF_OFF_PATH, "/solar/0")): selector.TextSelector(),
        vol.Required(CONF_DELAY_ON, default=data.get(CONF_DELAY_ON, DEFAULT_DELAY_ON)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=3600, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Required(CONF_DELAY_OFF, default=data.get(CONF_DELAY_OFF, DEFAULT_DELAY_OFF)):
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=3600, step=1, mode=selector.NumberSelectorMode.BOX)),
    })


class SmartDashboardSwitcherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        entries = self._async_current_entries()
        suggested_panel = PANEL_URL if not entries else f"{PANEL_URL}-{len(entries)+1}"
        if user_input is not None:
            panel = user_input[CONF_PANEL_URL].strip().strip("/")
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", panel) or panel in {"lovelace", "config", "developer-tools"}:
                return self.async_show_form(step_id="user", data_schema=_schema(user_input, suggested_panel), errors={CONF_PANEL_URL: "invalid_panel"})
            if any(e.data.get(CONF_PANEL_URL, PANEL_URL) == panel for e in entries):
                return self.async_show_form(step_id="user", data_schema=_schema(user_input, suggested_panel), errors={CONF_PANEL_URL: "panel_taken"})
            user_input[CONF_PANEL_URL] = panel
            for key in (CONF_ON_PATH, CONF_OFF_PATH):
                value = user_input[key].strip()
                if not value.startswith("/") or value.startswith("//") or "://" in value:
                    return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors={key: "invalid_path"})
                user_input[key] = value
            return self.async_create_entry(title=f"Smart Dashboard Switcher ({panel})", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}, suggested_panel))

    @staticmethod
    def async_get_options_flow(config_entry):
        return SmartDashboardSwitcherOptionsFlow(config_entry)


class SmartDashboardSwitcherOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            for key in (CONF_ON_PATH, CONF_OFF_PATH):
                value = user_input[key].strip()
                if not value.startswith("/") or value.startswith("//") or "://" in value:
                    return self.async_show_form(step_id="init", data_schema=_options_schema(user_input), errors={key: "invalid_path"})
                user_input[key] = value
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=_options_schema({**self._entry.data, **self._entry.options}))


def _options_schema(data):
    schema = _schema(data).schema.copy()
    for key in list(schema):
        if str(key) == CONF_PANEL_URL:
            del schema[key]
    return vol.Schema(schema)
