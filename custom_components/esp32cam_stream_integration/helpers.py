def normalize_base_url(host):
    host = host.strip().rstrip("/")
    if host.startswith(("http://", "https://")):
        return host
    return f"http://{host}"


def build_device_info(name, host, base_url):
    return {
        "identifiers": {("esp32cam_stream_integration", host)},
        "manufacturer": "Espressif",
        "model": "ESP32-CAM",
        "name": name,
        "configuration_url": base_url,
    }
