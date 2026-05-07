from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
import logging

from .coordinator import CameraCoordinator
from .const import (
    CONF_BASE_URL,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_CAMERA_NAME,
    DOMAIN,
    PLATFORMS,
)
from .helpers import normalize_base_url

_LOGGER = logging.getLogger(__name__)


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


def _get_go2rtc_camera_name(entry: ConfigEntry):
    for source in (entry.options, entry.data):
        go2rtc_camera_name = source.get(CONF_GO2RTC_CAMERA_NAME)
        if isinstance(go2rtc_camera_name, str) and go2rtc_camera_name.strip():
            return go2rtc_camera_name.strip()

    return entry.data[CONF_NAME]


def _get_go2rtc_base_url(entry: ConfigEntry):
    for source in (entry.options, entry.data):
        go2rtc_base_url = source.get(CONF_GO2RTC_BASE_URL)
        if isinstance(go2rtc_base_url, str) and go2rtc_base_url.strip():
            return normalize_base_url(go2rtc_base_url)

    return "http://localhost:1984"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    host = entry.data[CONF_HOST]
    base_url = normalize_base_url(host)
    go2rtc_base_url = _get_go2rtc_base_url(entry)
    go2rtc_camera_name = _get_go2rtc_camera_name(entry)
    _LOGGER.debug(
        "Using go2rtc camera name %r at %s for %s",
        go2rtc_camera_name,
        go2rtc_base_url,
        entry.title,
    )

    coordinator = CameraCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store shared data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        CONF_BASE_URL: base_url,
        CONF_GO2RTC_BASE_URL: go2rtc_base_url,
        "host": host,
        "name": entry.data[CONF_NAME],
        CONF_GO2RTC_CAMERA_NAME: go2rtc_camera_name,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None:
            await data["coordinator"].async_close()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
