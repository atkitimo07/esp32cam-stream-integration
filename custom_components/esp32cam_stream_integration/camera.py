from urllib.parse import urlencode

import aiohttp
import logging
from homeassistant.components.camera import Camera, CameraEntityFeature

from .const import CONF_BASE_URL, CONF_GO2RTC_BASE_URL, CONF_GO2RTC_CAMERA_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    base_url = hass.data[DOMAIN][entry.entry_id][CONF_BASE_URL]
    go2rtc_base_url = hass.data[DOMAIN][entry.entry_id][CONF_GO2RTC_BASE_URL]
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    host = hass.data[DOMAIN][entry.entry_id]["host"]
    go2rtc_camera_name = hass.data[DOMAIN][entry.entry_id][CONF_GO2RTC_CAMERA_NAME]

    async_add_entities([
        Esp32cam_stream_camera(
            name,
            base_url,
            go2rtc_base_url,
            host,
            go2rtc_camera_name,
        )
    ])


class Esp32cam_stream_camera(Camera):
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, name, base_url, go2rtc_base_url, host, go2rtc_camera_name):
        super().__init__()
        self._name = name
        self._base_url = base_url
        self._go2rtc_base_url = go2rtc_base_url
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
        stream_url = f"{self._go2rtc_base_url}/api/stream.mjpeg?{query}"
        _LOGGER.debug("Using go2rtc stream source %s", stream_url)
        return stream_url

    async def _fetch_image(self, session, url):
        try:
            _LOGGER.debug("Fetching snapshot from %s", url)
            async with session.get(url) as resp:
                image = await resp.read()
                _LOGGER.debug(
                    "Snapshot GET %s returned status=%s content_type=%s bytes=%s",
                    url,
                    resp.status,
                    resp.headers.get("Content-Type"),
                    len(image),
                )

                if resp.status != 200:
                    _LOGGER.warning(
                        "Snapshot GET %s failed with HTTP status %s",
                        url,
                        resp.status,
                    )
                    return None

                if not image:
                    _LOGGER.warning("Snapshot GET %s returned an empty response", url)
                    return None

                return image
        except TimeoutError:
            _LOGGER.warning("Snapshot GET %s timed out", url)
        except aiohttp.ClientError as err:
            _LOGGER.warning("Snapshot GET %s failed: %s", url, err)

        return None

    async def async_camera_image(self, width=None, height=None):
        _LOGGER.debug(
            "Camera image requested for %s width=%s height=%s",
            self.entity_id,
            width,
            height,
        )
        snapshot_url = f"{self._base_url}/snapshot"
        frame_query = {"src": self._go2rtc_camera_name}
        if width is not None:
            frame_query["width"] = width
        if height is not None:
            frame_query["height"] = height
        go2rtc_snapshot_url = (
            f"{self._go2rtc_base_url}/api/frame.jpeg?{urlencode(frame_query)}"
        )

        timeout = aiohttp.ClientTimeout(total=4, sock_connect=2, sock_read=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            image = await self._fetch_image(session, snapshot_url)
            if image is not None:
                return image

            _LOGGER.debug(
                "Falling back to go2rtc snapshot endpoint for %s",
                self._go2rtc_camera_name,
            )
            return await self._fetch_image(session, go2rtc_snapshot_url)
