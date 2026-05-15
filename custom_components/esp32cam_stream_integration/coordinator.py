import asyncio
import aiohttp
from datetime import timedelta
from io import BytesIO
import json
import logging
from time import monotonic
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from PIL import Image, UnidentifiedImageError

from .helpers import normalize_base_url

_LOGGER = logging.getLogger(__name__)

AVAILABILITY_FAILURE_THRESHOLD = 2

AUTO_NIGHT_VISION_ENABLED = "auto_night_vision_enabled"
AUTO_IR_LED_ENABLED = "auto_ir_led_enabled"
ANALYSIS_INTERVAL = "analysis_interval"
NIGHT_VISION_ON_THRESHOLD = "night_vision_on_threshold"
NIGHT_VISION_OFF_THRESHOLD = "night_vision_off_threshold"
IR_LED_ON_THRESHOLD = "ir_led_on_threshold"
IR_LED_OFF_THRESHOLD = "ir_led_off_threshold"
IR_LED_BRIGHTNESS = "ir_led_brightness"

DEFAULT_SETTINGS = {
    AUTO_NIGHT_VISION_ENABLED: False,
    AUTO_IR_LED_ENABLED: False,
    ANALYSIS_INTERVAL: 30,
    NIGHT_VISION_ON_THRESHOLD: 45,
    NIGHT_VISION_OFF_THRESHOLD: 65,
    IR_LED_ON_THRESHOLD: 35,
    IR_LED_OFF_THRESHOLD: 55,
    IR_LED_BRIGHTNESS: 75,
}


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


def _percentile(sorted_values, percentile):
    if not sorted_values:
        return None

    index = round((len(sorted_values) - 1) * percentile)
    return sorted_values[index]


def _analyze_snapshot(image_bytes):
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image = image.convert("RGB")
            image.thumbnail((160, 120))
            pixels = list(image.getdata())
    except (UnidentifiedImageError, OSError) as err:
        _LOGGER.debug("Unable to analyze snapshot: %s", err)
        return None

    if not pixels:
        return None

    luminance_values = []
    pink_values = []
    for red, green, blue in pixels:
        luminance_values.append(
            round((0.2126 * red) + (0.7152 * green) + (0.0722 * blue), 2)
        )
        pink_values.append(max((((red + blue) / 2) - green), 0))

    luminance_values.sort()
    pink_pixel_count = sum(1 for value in pink_values if value >= 30)

    return {
        "mean_luminance": round(sum(luminance_values) / len(luminance_values), 2),
        "median_luminance": round(_percentile(luminance_values, 0.5), 2),
        "p25_luminance": round(_percentile(luminance_values, 0.25), 2),
        "pink_index": round((sum(pink_values) / len(pink_values)) / 255 * 100, 2),
        "pink_pixel_percent": round(pink_pixel_count / len(pixels) * 100, 2),
    }


class CameraCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.hass = hass
        self.base_url = normalize_base_url(entry.data[CONF_HOST])
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

        image = await self._safe_get_bytes(f"{self.base_url}/snapshot")
        if image is None:
            return last_analysis

        analysis = await self.hass.async_add_executor_job(_analyze_snapshot, image)
        if analysis is None:
            return last_analysis

        self._last_image_analysis_at = now
        return analysis

    async def _apply_automatic_control(self, data):
        analysis = data.get("image_analysis", {})
        luminance = analysis.get("p25_luminance")
        if luminance is None:
            return

        night_vision_state = data.get("nightvision", {}).get("state")
        night_vision_on = bool(night_vision_state) if night_vision_state is not None else False
        ir_state = data.get("irled", {}).get("state")
        ir_on = bool(ir_state) if ir_state is not None else False
        night_vision_changed = False

        if self.settings[AUTO_NIGHT_VISION_ENABLED]:
            if not night_vision_on and luminance <= self.settings[NIGHT_VISION_ON_THRESHOLD]:
                if await self._safe_set_state("nightvision", 1):
                    data["nightvision"]["state"] = 1
                    night_vision_on = True
                    night_vision_changed = True
                    self._last_image_analysis_at = 0
            elif night_vision_on and luminance >= self.settings[NIGHT_VISION_OFF_THRESHOLD]:
                if await self._safe_set_state("nightvision", 0):
                    data["nightvision"]["state"] = 0
                    night_vision_on = False
                    night_vision_changed = True
                    self._last_image_analysis_at = 0

        if not night_vision_on:
            if ir_on:
                if await self._safe_set_state("irled", 0):
                    data["irled"]["state"] = 0
            return

        if night_vision_changed or not self.settings[AUTO_IR_LED_ENABLED]:
            return

        if not ir_on and luminance <= self.settings[IR_LED_ON_THRESHOLD]:
            brightness = round(self.settings[IR_LED_BRIGHTNESS] / 100, 3)
            if await self._safe_set_state("irled", brightness):
                data["irled"]["state"] = brightness
        elif ir_on and luminance >= self.settings[IR_LED_OFF_THRESHOLD]:
            if await self._safe_set_state("irled", 0):
                data["irled"]["state"] = 0

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
