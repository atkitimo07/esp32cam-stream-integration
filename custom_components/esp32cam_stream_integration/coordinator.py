from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import aiohttp
from datetime import timedelta

class CameraCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host):
        self.host = host

        super().__init__(
            hass,
            logger=None,
            name="esp32cam_stream_integration",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://{self.host}/status") as resp:
                return await resp.json()