from homeassistant.components.light import LightEntity
import aiohttp

class IRLight(LightEntity):
    def __init__(self, name, host):
        self._name = name
        self._host = host
        self._brightness = 0

    @property
    def name(self):
        return f"{self._name} IR LED"

    @property
    def brightness(self):
        return self._brightness

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get("brightness", 255) / 255
        self._brightness = brightness

        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/irled?state={brightness}")

    async def async_turn_off(self, **kwargs):
        self._brightness = 0

        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/irled?state=0")