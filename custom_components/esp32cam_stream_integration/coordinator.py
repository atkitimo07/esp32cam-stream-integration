import asyncio
import aiohttp
from datetime import timedelta
import json
import logging
from time import monotonic
from urllib.parse import urlencode

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auto_control import ANALYSIS_INTERVAL, DEFAULT_SETTINGS, analyze_snapshot, assign_auto_control_actions
from .const import CONF_GO2RTC_BASE_URL, CONF_GO2RTC_CAMERA_NAME
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
        self.hass = hass
        self.base_url = normalize_base_url(entry.data[CONF_HOST])
        self.go2rtc_base_url = self._get_go2rtc_base_url(entry)
        self.go2rtc_camera_name = self._get_go2rtc_camera_name(entry)
        self._last_data = None
        self._last_image_analysis_at = 0
        self._available = False
        self._availability_failures = 0
        self.settings = DEFAULT_SETTINGS.copy()

        super().__init__(
            hass,
            logger=_LOGGER,
            name="esp32cam_stream_integration",
            update_interval=timedelta(seconds=5),
        )

        self.session = aiohttp.ClientSession()

    def _get_go2rtc_base_url(self, entry):
        for source in (entry.options, entry.data):
            go2rtc_base_url = source.get(CONF_GO2RTC_BASE_URL)
            if isinstance(go2rtc_base_url, str) and go2rtc_base_url.strip():
                return normalize_base_url(go2rtc_base_url)

        return "http://localhost:1984"

    def _get_go2rtc_camera_name(self, entry):
        for source in (entry.options, entry.data):
            go2rtc_camera_name = source.get(CONF_GO2RTC_CAMERA_NAME)
            if isinstance(go2rtc_camera_name, str) and go2rtc_camera_name.strip():
                return go2rtc_camera_name.strip()

        return entry.data[CONF_NAME]

    def _go2rtc_snapshot_url(self):
        query = urlencode({"src": self.go2rtc_camera_name})
        return f"{self.go2rtc_base_url}/api/frame.jpeg?{query}"

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

    async def _safe_get_bytes(self, url):
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.debug(
                        "Bytes GET %s returned HTTP status %s",
                        url,
                        resp.status,
                    )
                    return None
                return await resp.read()
        except Exception as err:
            _LOGGER.debug("Failed bytes GET %s: %r", url, err)
            return None

    async def _safe_set_state(self, path, state):
        url = f"{self.base_url}/{path}?state={state}"
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Control GET %s returned HTTP status %s", url, resp.status)
                    return False
                return True
        except Exception as err:
            _LOGGER.debug("Failed control GET %s: %r", url, err)
            return False

    def _update_availability(self, probe_success):
        if probe_success:
            self._availability_failures = 0
            self._available = True
            return

        self._availability_failures += 1
        if (self._availability_failures >= AVAILABILITY_FAILURE_THRESHOLD):
            self._available = False

    def update_setting(self, key, value):
        self.settings[key] = value
        self.async_set_updated_data(self._with_settings(self.data or self._last_data or {}))

    def _with_settings(self, data):
        updated = dict(data)
        updated["settings"] = self.settings.copy()
        return updated

    async def _maybe_analyze_snapshot(self):
        now = monotonic()
        last_analysis = {}
        if self._last_data is not None:
            last_analysis = self._last_data.get("image_analysis", {})

        interval = self.settings[ANALYSIS_INTERVAL]
        if last_analysis and now - self._last_image_analysis_at < interval:
            return last_analysis

        image = await self._safe_get_bytes(self._go2rtc_snapshot_url())
        if image is None:
            return last_analysis

        analysis = await self.hass.async_add_executor_job(analyze_snapshot, image)
        if analysis is None:
            return last_analysis

        self._last_image_analysis_at = now
        return analysis

    async def _apply_automatic_control(self, data):
        night_vision_state = data.get("nightvision", {}).get("state")
        night_vision_on = bool(night_vision_state) if night_vision_state is not None else False
        ir_state = data.get("irled", {}).get("state")
        ir_on = bool(ir_state) if ir_state is not None else False
        actions = assign_auto_control_actions(
            self.settings,
            data.get("image_analysis", {}),
            night_vision_on,
            ir_on,
        )

        for action in actions:
            if await self._safe_set_state(action.path, action.state):
                if action.path == "nightvision":
                    data["nightvision"]["state"] = action.state
                    self._last_image_analysis_at = 0
                elif action.path == "irled":
                    data["irled"]["state"] = action.state

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

        self._update_availability(ir_raw is not None or nv_raw is not None or status is not None)

        # Normalise safely
        data = {
            "available": self._available,
            "status": status or {},

            "irled": {
                "state": _parse_float(ir_raw)
            },

            "nightvision": {
                "state": _parse_int(nv_raw)
            },

            "image_analysis": {},
        }

        if self._last_data is not None:
            if not data["status"]:
                data["status"] = self._last_data.get("status", {})
            for key in ("irled", "nightvision"):
                if data[key]["state"] is None:
                    data[key]["state"] = self._last_data.get(key, {}).get("state")

            if (
                data["nightvision"]["state"]
                != self._last_data.get("nightvision", {}).get("state")
            ):
                self._last_image_analysis_at = 0

        data["image_analysis"] = await self._maybe_analyze_snapshot()

        await self._apply_automatic_control(data)

        data = self._with_settings(data)
        self._last_data = data
        return data

    async def async_close(self):
        await self.session.close()
