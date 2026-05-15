from urllib.parse import urlencode

import aiohttp
import asyncio
import logging
from aiohttp import web
from homeassistant.components.camera import Camera
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BASE_URL, CONF_GO2RTC_BASE_URL, CONF_GO2RTC_CAMERA_NAME, DOMAIN
from .helpers import build_device_info

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
    def __init__(self, name, base_url, go2rtc_base_url, host, go2rtc_camera_name):
        super().__init__()
        self._name = name
        self._base_url = base_url
        self._go2rtc_base_url = go2rtc_base_url
        self._host = host
        self._go2rtc_camera_name = go2rtc_camera_name
        self._attr_device_info = build_device_info(name, host, base_url)

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"{self._host}_camera"

    def _mjpeg_stream_url(self):
        query = urlencode({"src": self._go2rtc_camera_name})
        return f"{self._go2rtc_base_url}/api/stream.mjpeg?{query}"

    def _snapshot_url(self):
        query = urlencode({"src": self._go2rtc_camera_name})
        return f"{self._go2rtc_base_url}/api/frame.jpeg?{query}"

    async def handle_async_mjpeg_stream(self, request):
        stream_url = self._mjpeg_stream_url()
        _LOGGER.debug("Proxying go2rtc MJPEG stream %s", stream_url)
        session = async_get_clientsession(self.hass)

        upstream = None
        response = web.StreamResponse()

        try:
            upstream = await session.get(stream_url)
            response.set_status(upstream.status)

            content_type = upstream.headers.get("Content-Type")
            if content_type:
                response.headers["Content-Type"] = content_type
            else:
                response.headers["Content-Type"] = "multipart/x-mixed-replace"

            await response.prepare(request)

            async for chunk in upstream.content.iter_chunked(8192):
                await response.write(chunk)

            return response
        except asyncio.CancelledError:
            _LOGGER.debug("MJPEG stream client disconnected for %s", self.entity_id)
            raise
        except (ConnectionResetError, BrokenPipeError):
            _LOGGER.debug("MJPEG stream client disconnected for %s", self.entity_id)
            return response
        except aiohttp.ClientConnectionError as err:
            if upstream is not None:
                _LOGGER.debug(
                    "MJPEG upstream stream closed for %s: %s",
                    self.entity_id,
                    err,
                )
                return response
            _LOGGER.warning("MJPEG stream request failed for %s: %s", stream_url, err)
            raise
        except aiohttp.ClientError as err:
            _LOGGER.warning("MJPEG stream request failed for %s: %s", stream_url, err)
            raise
        finally:
            if upstream is not None:
                upstream.close()
                _LOGGER.debug("Closed go2rtc MJPEG stream for %s", self.entity_id)

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

        timeout = aiohttp.ClientTimeout(total=10, sock_connect=5, sock_read=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return await self._fetch_image(session, self._snapshot_url())
