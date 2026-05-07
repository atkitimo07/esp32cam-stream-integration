from homeassistant.components.light import ColorMode, LightEntity
import aiohttp
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([
        IRLight(name, host, coordinator)
    ])

class IRLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, name, host, coordinator):
        self._name = name
        self._host = host
        self.coordinator = coordinator

    @property
    def name(self):
        return f"{self._name} IR LED"

    @property
    def unique_id(self):
        return f"{self._host}_ir_led"

    @property
    def brightness(self):
        value = self.coordinator.data["irled"]["state"]
        return 0 if value is None else value * 255

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get("brightness", 255) / 255

        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/irled?state={brightness}")

    async def async_turn_off(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/irled?state=0")
