from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from .coordinator import CameraCoordinator
from .const import CONF_GO2RTC_CAMERA_NAME, DOMAIN, PLATFORMS


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    host = entry.data[CONF_HOST]
    go2rtc_camera_name = entry.options.get(
        CONF_GO2RTC_CAMERA_NAME,
        entry.data.get(CONF_GO2RTC_CAMERA_NAME, entry.data[CONF_NAME]),
    )

    coordinator = CameraCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store shared data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
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
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["coordinator"].async_close()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
