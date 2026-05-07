from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import asyncio
import aiohttp
from datetime import timedelta
import json
import logging
from homeassistant.const import CONF_HOST

from .helpers import normalize_base_url

_LOGGER = logging.getLogger(__name__)


def _parse_float(value):
    if value in (None, "", "null"):
        return None

    if isinstance(value, dict):
        value = value.get("state")

    if isinstance(value, str):
        value = value.strip()
        if value.startswith("{"):
            try:
                return _parse_float(json.loads(value))
            except json.JSONDecodeError:
                pass

    try:
        return float(value)
    except (TypeError, ValueError):
        _LOGGER.debug("Unable to parse float value: %r", value)
        return None


def _parse_int(value):
    parsed = _parse_float(value)
    return int(parsed) if parsed is not None else None


class CameraCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.base_url = normalize_base_url(entry.data[CONF_HOST])

        super().__init__(
            hass,
            logger=_LOGGER,
            name="esp32cam_stream_integration",
            update_interval=timedelta(seconds=5),
        )

        self.session = aiohttp.ClientSession()

    async def _safe_get_text(self, url):
        try:
            async with self.session.get(url, timeout=2) as resp:
                return await resp.text()
        except Exception as err:
            _LOGGER.debug("Failed GET %s: %r", url, err)
            return None

    async def _safe_get_json(self, url):
        try:
            async with self.session.get(url, timeout=2) as resp:
                return await resp.json()
        except Exception as err:
            _LOGGER.debug("Failed JSON GET %s: %r", url, err)
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
                "state": _parse_float(ir_raw)
            },

            "nightvision": {
                "state": _parse_int(nv_raw)
            }
        }

    async def async_close(self):
        await self.session.close()
