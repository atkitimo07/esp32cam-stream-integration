from homeassistant.components.camera import Camera
import aiohttp
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]

    async_add_entities([
        Esp32cam_stream_camera(name, host)
    ])

class Esp32cam_stream_camera(Camera):
    def __init__(self, name, host):
        self._name = name
        self._host = host

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._host}_ir_led"

    async def async_camera_image(self):
        url = f"http://{self._host}/snapshot"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.read()
