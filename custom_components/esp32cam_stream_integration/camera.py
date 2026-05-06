from homeassistant.components.camera import Camera
import aiohttp

class Esp32cam_stream_camera(Camera):
    def __init__(self, name, host):
        self._name = name
        self._host = host

    @property
    def name(self):
        return self._name

    async def async_camera_image(self):
        url = f"http://{self._host}/snapshot"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.read()