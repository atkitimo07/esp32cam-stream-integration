from dataclasses import dataclass
from io import BytesIO
import logging

from PIL import Image, UnidentifiedImageError

_LOGGER = logging.getLogger(__name__)

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
    NIGHT_VISION_OFF_THRESHOLD: 120,
    IR_LED_ON_THRESHOLD: 35,
    IR_LED_OFF_THRESHOLD: 130,
    IR_LED_BRIGHTNESS: 75,
}


@dataclass(frozen=True)
class ControlAction:
    path: str
    state: float | int


def percentile(sorted_values, percentile_value):
    if not sorted_values:
        return None

    index = round((len(sorted_values) - 1) * percentile_value)
    return sorted_values[index]


def analyze_snapshot(image_bytes):
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
        "median_luminance": round(percentile(luminance_values, 0.5), 2),
        "p25_luminance": round(percentile(luminance_values, 0.25), 2),
        "pink_index": round((sum(pink_values) / len(pink_values)) / 255 * 100, 2),
        "pink_pixel_percent": round(pink_pixel_count / len(pixels) * 100, 2),
    }


def assign_auto_control_actions(settings, analysis, night_vision_on, ir_led_on):
    luminance = analysis.get("p25_luminance")
    if luminance is None:
        return []

    actions = []
    night_vision_changed = False

    if settings[AUTO_NIGHT_VISION_ENABLED]:
        # If night vision off and image is dark:
        if not night_vision_on and luminance <= settings[NIGHT_VISION_ON_THRESHOLD]:
            actions.append(ControlAction("nightvision", 1))
            night_vision_on = True
            night_vision_changed = True
        # If night vision is on, and LED is off, and image is bright:
        elif night_vision_on and not ir_led_on and luminance >= settings[NIGHT_VISION_OFF_THRESHOLD]:
            actions.append(ControlAction("nightvision", 0))
            night_vision_on = False
            night_vision_changed = True
            if ir_led_on and settings[AUTO_IR_LED_ENABLED]:
                actions.append(ControlAction("irled", 0))
        
        # Only control LED if night vision if already on
        elif night_vision_on and settings[AUTO_IR_LED_ENABLED]:
            # If LED off and image is dark:
            if not ir_led_on and luminance <= settings[IR_LED_ON_THRESHOLD]:
                actions.append(ControlAction("irled", round(settings[IR_LED_BRIGHTNESS] / 100, 3)))
            # If LED is on and image is bright:
            elif ir_led_on and luminance >= settings[IR_LED_OFF_THRESHOLD]:
                actions.append(ControlAction("irled", 0))

    return actions
