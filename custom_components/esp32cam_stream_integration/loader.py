from .camera import Esp32cam_stream_camera
from .coordinator import CameraCoordinator

async def async_setup_entry(hass, entry, async_add_entities):
    host = entry.data["host"]
    name = entry.data["name"]

    async_add_entities([
        Esp32cam_stream_camera(name, host)
    ])