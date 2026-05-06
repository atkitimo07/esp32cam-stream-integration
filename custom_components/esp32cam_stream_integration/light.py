from homeassistant.components.light import LightEntity
import aiohttp

class IRLight(LightEntity):
    def __init__(self, name, host, coordinator):
        self._name = name
        self._host = host
        self.coordinator = coordinator

    @property
    def name(self):
        return f"{self._name} IR LED"

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