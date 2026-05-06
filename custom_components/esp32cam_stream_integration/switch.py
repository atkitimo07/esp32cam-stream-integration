from homeassistant.components.switch import SwitchEntity
import aiohttp

class NightVisionSwitch(SwitchEntity):
    def __init__(self, name, host, coordinator):
        self._name = name
        self._host = host
        self.coordinator = coordinator

    @property
    def name(self):
        return f"{self._name} Night Vision"

    @property
    def is_on(self):
        value = self.coordinator.data["nightvision"]["state"]
        return bool(value) if value is not None else False

    async def async_turn_on(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/nightvision?state=1")

    async def async_turn_off(self, **kwargs):
        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/nightvision?state=0")