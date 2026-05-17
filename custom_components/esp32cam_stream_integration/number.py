from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTime
from homeassistant.helpers.restore_state import RestoreEntity

from .auto_control import (
    ANALYSIS_INTERVAL,
    IR_LED_BRIGHTNESS,
    IR_LED_ON_THRESHOLD,
    IR_LED_PINK_OFF_THRESHOLD,
    NIGHT_VISION_ON_THRESHOLD,
    NIGHT_VISION_PINK_OFF_THRESHOLD,
)
from .const import CONF_BASE_URL, DOMAIN
from .helpers import build_device_info


NUMBER_METADATA = {
    ANALYSIS_INTERVAL: {
        "name": "Image Analysis Interval",
        "min": 10,
        "max": 300,
        "step": 5,
        "unit": UnitOfTime.SECONDS,
    },
    NIGHT_VISION_ON_THRESHOLD: {
        "name": "Night Vision On Threshold",
        "min": 0,
        "max": 255,
        "step": 1,
    },
    NIGHT_VISION_PINK_OFF_THRESHOLD: {
        "name": "Night Vision Pink Pixels Off Threshold",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
    },
    IR_LED_ON_THRESHOLD: {
        "name": "IR LED On Threshold",
        "min": 0,
        "max": 255,
        "step": 1,
    },
    IR_LED_PINK_OFF_THRESHOLD: {
        "name": "IR LED Pink Pixels Off Threshold",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
    },
    IR_LED_BRIGHTNESS: {
        "name": "IR LED Auto Brightness",
        "min": 1,
        "max": 100,
        "step": 1,
        "unit": PERCENTAGE,
    },
}


async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        AutoControlNumber(name, host, base_url, coordinator, key)
        for key in NUMBER_METADATA
    ])


class AutoControlNumber(RestoreEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER

    def __init__(self, name, host, base_url, coordinator, key):
        self._name = name
        self._host = host
        self._coordinator = coordinator
        self._key = key
        self._attr_device_info = build_device_info(name, host, base_url)

        metadata = NUMBER_METADATA[key]
        self._attr_native_min_value = metadata["min"]
        self._attr_native_max_value = metadata["max"]
        self._attr_native_step = metadata["step"]
        self._attr_native_unit_of_measurement = metadata.get("unit")

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        try:
            value = float(last_state.state)
        except (TypeError, ValueError):
            return

        metadata = NUMBER_METADATA[self._key]
        if value < metadata["min"] or value > metadata["max"]:
            return

        self._coordinator.update_setting(self._key, value)

    @property
    def name(self):
        return f"{self._name} {NUMBER_METADATA[self._key]['name']}"

    @property
    def unique_id(self):
        return f"{self._host}_{self._key}"

    @property
    def available(self):
        return bool(self._coordinator.data.get("available"))

    @property
    def native_value(self):
        return self._coordinator.settings[self._key]

    async def async_set_native_value(self, value):
        self._coordinator.update_setting(self._key, value)
        self.async_write_ha_state()
        await self._coordinator.async_request_refresh()
