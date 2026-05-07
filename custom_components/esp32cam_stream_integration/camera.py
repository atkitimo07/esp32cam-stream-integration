from urllib.parse import urlencode

import aiohttp
import logging
from homeassistant.components.camera import Camera, CameraEntityFeature

from .const import CONF_BASE_URL, CONF_GO2RTC_CAMERA_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    go2rtc_camera_name = hass.data[DOMAIN][entry.entry_id][CONF_GO2RTC_CAMERA_NAME]

    async_add_entities([
        Esp32cam_stream_camera(name, base_url, host, go2rtc_camera_name)
    ])


class Esp32cam_stream_camera(Camera):
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, name, base_url, host, go2rtc_camera_name):
        super().__init__()
        self._name = name
        self._base_url = base_url
        self._host = host
        self._go2rtc_camera_name = go2rtc_camera_name

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._host}_camera"

    async def stream_source(self):
        query = urlencode({"src": self._go2rtc_camera_name})
        stream_url = f"http://localhost:1984/api/stream.mjpeg?{query}"
        _LOGGER.debug("Using go2rtc stream source %s", stream_url)
        return stream_url

    async def async_camera_image(self):
        url = f"{self._base_url}/snapshot"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.read()
