from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BASE_URL, DOMAIN
from .coordinator import IR_LED_ON_THRESHOLD, NIGHT_VISION_ON_THRESHOLD
from .helpers import build_device_info


BINARY_SENSOR_METADATA = {
    "night_vision_image_dark": {
        "name": "Night Vision Image Dark",
        "threshold": NIGHT_VISION_ON_THRESHOLD,
    },
    "ir_led_image_dark": {
        "name": "IR LED Image Dark",
        "threshold": IR_LED_ON_THRESHOLD,
    },
}


async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        ImageDarkBinarySensor(name, host, base_url, coordinator, key)
        for key in BINARY_SENSOR_METADATA
    ])


class ImageDarkBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, name, host, base_url, coordinator, key):
        super().__init__(coordinator)
        self._name = name
        self._host = host
        self._key = key
        self._attr_device_info = build_device_info(name, host, base_url)

    @property
    def name(self):
        return f"{self._name} {BINARY_SENSOR_METADATA[self._key]['name']}"

    @property
    def unique_id(self):
        return f"{self._host}_{self._key}"

    @property
    def available(self):
        return (
            bool(self.coordinator.data.get("available"))
            and self.coordinator.data.get("image_analysis", {}).get("p25_luminance") is not None
        )

    @property
    def is_on(self):
        luminance = self.coordinator.data.get("image_analysis", {}).get("p25_luminance")
        if luminance is None:
            return False

        threshold_key = BINARY_SENSOR_METADATA[self._key]["threshold"]
        return luminance <= self.coordinator.settings[threshold_key]
