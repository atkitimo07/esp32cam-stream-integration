from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import aiohttp

from .auto_control import AUTO_IR_LED_ENABLED, AUTO_NIGHT_VISION_ENABLED
from .const import CONF_BASE_URL, DOMAIN
from .helpers import build_device_info


AUTO_SWITCHES = {
    AUTO_NIGHT_VISION_ENABLED: "Auto Night Vision",
    AUTO_IR_LED_ENABLED: "Auto IR LED",
}


async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        NightVisionSwitch(name, base_url, host, coordinator),
        AutoControlSwitch(name, host, base_url, coordinator, AUTO_NIGHT_VISION_ENABLED),
        AutoControlSwitch(name, host, base_url, coordinator, AUTO_IR_LED_ENABLED),
    ])


class NightVisionSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, name, base_url, host, coordinator):
        super().__init__(coordinator)
        self._name = name
        self._base_url = base_url
        self._host = host
        self._attr_device_info = build_device_info(name, host, base_url)

    @property
    def name(self):
        return f"{self._name} Night Vision"

    @property
    def unique_id(self):
        return f"{self._host}_night_vision"

    @property
    def available(self):
        return bool(self.coordinator.data.get("available"))

    @property
    def is_on(self):
        value = self.coordinator.data.get("nightvision", {}).get("state")
        return bool(value) if value is not None else False

    async def async_turn_on(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"{self._base_url}/nightvision?state=1")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"{self._base_url}/nightvision?state=0")
            await session.get(f"{self._base_url}/irled?state=0")
        await self.coordinator.async_request_refresh()


class AutoControlSwitch(CoordinatorEntity, RestoreEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, name, host, base_url, coordinator, key):
        super().__init__(coordinator)
        self._name = name
        self._host = host
        self._key = key
        self._attr_device_info = build_device_info(name, host, base_url)

    async def async_added_to_hass(self):
        await CoordinatorEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.coordinator.update_setting(self._key, last_state.state == "on")

    @property
    def name(self):
        return f"{self._name} {AUTO_SWITCHES[self._key]}"

    @property
    def unique_id(self):
        return f"{self._host}_{self._key}"

    @property
    def available(self):
        return bool(self.coordinator.data.get("available"))

    @property
    def is_on(self):
        return bool(self.coordinator.settings[self._key])

    @callback
    def _set_enabled(self, enabled):
        self.coordinator.update_setting(self._key, enabled)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        self._set_enabled(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        self._set_enabled(False)
        await self.coordinator.async_request_refresh()
