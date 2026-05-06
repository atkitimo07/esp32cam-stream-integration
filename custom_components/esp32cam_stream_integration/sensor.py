from homeassistant.components.sensor import SensorEntity

class StatusSensor(SensorEntity):
    def __init__(self, name, key, coordinator):
        self._name = name
        self._key = key
        self.coordinator = coordinator

    @property
    def name(self):
        return f"{self._name} {self._key}"

    @property
    def state(self):
        status = self.coordinator.data.get("status", {})
        return status.get(self._key)