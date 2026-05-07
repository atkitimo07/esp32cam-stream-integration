from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import aiohttp

from .const import CONF_BASE_URL, DOMAIN
from .helpers import build_device_info

async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        NightVisionSwitch(name, base_url, host, coordinator)
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
        await self.coordinator.async_request_refresh()
