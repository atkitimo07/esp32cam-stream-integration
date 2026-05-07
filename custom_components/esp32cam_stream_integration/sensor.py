from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

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

    @property
    def name(self):
        return f"{self._name} {self._key}"

    @property
    def unique_id(self):
        return f"{self._host}_{self._key}"

    @property
    def native_value(self):
        status = self.coordinator.data.get("status", {})
        return status.get(self._key)
