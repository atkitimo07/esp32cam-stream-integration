from homeassistant.components.light import ColorMode, LightEntity
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
        IRLight(name, base_url, host, coordinator)
    ])


class IRLight(CoordinatorEntity, LightEntity):
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, name, base_url, host, coordinator):
        super().__init__(coordinator)
        self._name = name
        self._base_url = base_url
        self._host = host
        self._attr_device_info = build_device_info(name, host, base_url)

    @property
    def name(self):
        return f"{self._name} IR LED"

    @property
    def unique_id(self):
        return f"{self._host}_ir_led"

    @property
    def available(self):
        return bool(self.coordinator.data and self.coordinator.data.get("available"))

    @property
    def brightness(self):
        value = self.coordinator.data.get("irled", {}).get("state")
        return 0 if value is None else round(value * 255)

    @property
    def is_on(self):
        value = self.coordinator.data.get("irled", {}).get("state")
        return bool(value) if value is not None else False

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get("brightness", 255) / 255

        async with aiohttp.ClientSession() as session:
            await session.get(f"{self._base_url}/irled?state={brightness}")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"{self._base_url}/irled?state=0")
        await self.coordinator.async_request_refresh()
