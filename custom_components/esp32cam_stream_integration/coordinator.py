from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import asyncio
import aiohttp
from datetime import timedelta
import json
import logging
from homeassistant.const import CONF_HOST

from .helpers import normalize_base_url

_LOGGER = logging.getLogger(__name__)

AVAILABILITY_FAILURE_THRESHOLD = 2


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
        self._last_data = None
        self._available = False
        self._availability_failures = 0

        super().__init__(
            hass,
            logger=_LOGGER,
            name="esp32cam_stream_integration",
            update_interval=timedelta(seconds=5),
        )

        self.session = aiohttp.ClientSession()

    async def _safe_get_text(self, url):
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.debug("GET %s returned HTTP status %s", url, resp.status)
                    return None
                return await resp.text()
        except Exception as err:
            _LOGGER.debug("Failed GET %s: %r", url, err)
            return None

    async def _safe_get_json(self, url):
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "JSON GET %s returned HTTP status %s",
                        url,
                        resp.status,
                    )
                    return None
                return await resp.json()
        except Exception as err:
            _LOGGER.debug("Failed JSON GET %s: %r", url, err)
            return None

    def _update_availability(self, probe_success):
        if probe_success:
            self._availability_failures = 0
            self._available = True
            return

        self._availability_failures += 1
        if (
            not self._available
            or self._availability_failures >= AVAILABILITY_FAILURE_THRESHOLD
        ):
            self._available = False

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

        # /status can miss responses during streaming, so availability is based on
        # the lightweight state endpoints that prove the firmware HTTP app responds.
        self._update_availability(ir_raw is not None or nv_raw is not None)

        # Normalise safely
        data = {
            "available": self._available,
            "status": status or {},

            "irled": {
                "state": _parse_float(ir_raw)
            },

            "nightvision": {
                "state": _parse_int(nv_raw)
            }
        }

        if self._last_data is not None:
            if not data["status"]:
                data["status"] = self._last_data.get("status", {})
            for key in ("irled", "nightvision"):
                if data[key]["state"] is None:
                    data[key]["state"] = self._last_data.get(key, {}).get("state")

        self._last_data = data
        return data

    async def async_close(self):
        await self.session.close()
