from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


SENSOR_METADATA = {
    "fps": {
        "translation_key": "fps",
        "unit": "fps",
    },
    "rssi": {
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "translation_key": "rssi",
        "unit": "dBm",
    },
    "temp": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "translation_key": "temp",
        "unit": UnitOfTemperature.CELSIUS,
    },
}


def _parse_number(value):
    if value in (None, "", "null"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        StatusSensor(name, "fps", host, coordinator),
        StatusSensor(name, "rssi", host, coordinator),
        StatusSensor(name, "temp", host, coordinator)
    ])


class StatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, name, key, host, coordinator):
        super().__init__(coordinator)
        self._name = name
        self._key = key
        self._host = host
        metadata = SENSOR_METADATA[key]
        self._attr_device_class = metadata.get("device_class")
        self._attr_native_unit_of_measurement = metadata.get("unit")
        self._attr_translation_key = metadata["translation_key"]

    @property
    def name(self):
        return f"{self._name} {self._key}"

    @property
    def unique_id(self):
        return f"{self._host}_{self._key}"

    @property
    def native_value(self):
        status = self.coordinator.data.get("status", {})
        return _parse_number(status.get(self._key))
