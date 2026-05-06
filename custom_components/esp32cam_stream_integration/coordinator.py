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

        self.session = aiohttp.ClientSession()

    async def _safe_get_text(self, url):
        try:
            async with self.session.get(url, timeout=3) as resp:
                return await resp.text()
        except Exception as e:
            _LOGGER.debug("Failed GET %s: %s", url, e)
            return None

    async def _safe_get_json(self, url):
        try:
            async with self.session.get(url, timeout=3) as resp:
                return await resp.json()
        except Exception as e:
            _LOGGER.debug("Failed JSON GET %s: %s", url, e)
            return None

    async def _async_update_data(self):
        # Run concurrently but isolate failures per request
        status_task = self._safe_get_json(f"{self.base_url}/status")
        ir_task = self._safe_get_text(f"{self.base_url}/irled/state")
        nv_task = self._safe_get_text(f"{self.base_url}/nightvision/state")

        status, ir_raw, nv_raw = await asyncio.gather(
            status_task,
            ir_task,
            nv_task,
        )

        # Normalise safely
        return {
            "status": status or {},

            "irled": {
                "state": float(ir_raw) if ir_raw not in (None, "", "null") else None
            },

            "nightvision": {
                "state": int(float(nv_raw)) if nv_raw not in (None, "", "null") else None
            }
        }

    async def async_close(self):
        await self.session.close()
