def normalize_base_url(host):
    host = host.strip().rstrip("/")
    if host.startswith(("http://", "https://")):
        return host
    return f"http://{host}"
