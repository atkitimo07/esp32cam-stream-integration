import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import CONF_GO2RTC_CAMERA_NAME, DOMAIN


def _go2rtc_camera_name_from_input(user_input, fallback_name):
    go2rtc_camera_name = user_input.get(CONF_GO2RTC_CAMERA_NAME, "").strip()
    if go2rtc_camera_name:
        return go2rtc_camera_name
    return fallback_name


class ESP32CAMStreamIntegrationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ESP32CAMStreamIntegrationOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            user_input[CONF_GO2RTC_CAMERA_NAME] = _go2rtc_camera_name_from_input(
                user_input,
                user_input[CONF_NAME],
            )
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_GO2RTC_CAMERA_NAME, default=""): str,
            }),
        )


class ESP32CAMStreamIntegrationOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_GO2RTC_CAMERA_NAME: _go2rtc_camera_name_from_input(
                        user_input,
                        self.config_entry.data[CONF_NAME],
                    )
                },
            )

        go2rtc_camera_name = self.config_entry.options.get(
            CONF_GO2RTC_CAMERA_NAME,
            self.config_entry.data.get(
                CONF_GO2RTC_CAMERA_NAME,
                self.config_entry.data[CONF_NAME],
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_GO2RTC_CAMERA_NAME,
                    default=go2rtc_camera_name,
                ): str,
            }),
        )
