from homeassistant.components.switch import SwitchEntity
import aiohttp

class NightVisionSwitch(SwitchEntity):
    def __init__(self, name, host):
        self._name = name
        self._host = host
        self._is_on = False

    @property
    def name(self):
        return f"{self._name} Night Vision"

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/nightvision?state=1")

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        async with aiohttp.ClientSession() as session:
            await session.get(f"http://{self._host}/nightvision?state=0")