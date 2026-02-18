from dataclasses import dataclass
from enum import StrEnum
from typing import List, Tuple

# CoreWLAN-compatible band identifiers
CHANNEL_BAND_24 = 1
CHANNEL_BAND_5 = 2
CHANNEL_BAND_6 = 3

# X-axis bounds used by the frontend
CHANNEL_NUMBER_MAX_24 = 16
CHANNEL_NUMBER_MAX_5 = 170
CHANNEL_NUMBER_MAX_6 = 233


def channel_half_span_for_width(width_mhz: int | None) -> int:
    """Convert MHz channel width into half-span measured in channel number steps.

    Channel numbers across 2.4/5/6 GHz are spaced 5 MHz apart. A 20 MHz channel
    covers ~4 channel steps total, so half-span is 2; 40 MHz -> 4; 80 -> 8; 160 -> 16.
    """
    if not width_mhz:
        width_mhz = 20
    # total span in channel steps (5 MHz per step)
    total_steps = int(round(width_mhz / 5))
    half = max(1, total_steps // 2)
    return half


def get_channel_block(
    primary_channel: int, width_mhz: int, band: int, span_direction: str | None
) -> Tuple[int, int]:
    """Calculate the actual channel block for a given primary channel and width.

    WiFi channels occupy predefined blocks, especially for wider channels.
    Returns (left, right) channel numbers for the block.
    """
    if width_mhz == 20:
        # 20 MHz: narrow span around the primary channel
        return (primary_channel - 2, primary_channel + 2)

    if band == CHANNEL_BAND_24:
        # 2.4 GHz 40 MHz channels
        # HT40+ uses primary + extension above, HT40- uses primary + extension below
        if width_mhz == 40:
            # 40MHz spans 8 channels total (40MHz / 5MHz per channel)
            if span_direction == "upper":
                return (primary_channel - 2, primary_channel + 6)
            elif span_direction == "lower":
                return (primary_channel - 6, primary_channel + 2)
            else:
                # default to upper if primary channel is low, lower if primary channel is high
                if primary_channel <= 7:
                    return (primary_channel - 2, primary_channel + 6)
                else:
                    return (primary_channel - 6, primary_channel + 2)

    if band == CHANNEL_BAND_5:
        # 5 GHz uses specific channel blocks for 40/80/160 MHz widths
        if width_mhz == 40:
            # 40 MHz blocks
            if 36 <= primary_channel <= 40:
                return (34, 42)
            elif 44 <= primary_channel <= 48:
                return (42, 50)
            elif 52 <= primary_channel <= 56:
                return (50, 58)
            elif 60 <= primary_channel <= 64:
                return (58, 66)
            elif 100 <= primary_channel <= 104:
                return (98, 106)
            elif 108 <= primary_channel <= 112:
                return (106, 114)
            elif 116 <= primary_channel <= 120:
                return (114, 122)
            elif 124 <= primary_channel <= 128:
                return (122, 130)
            elif 132 <= primary_channel <= 136:
                return (130, 138)
            elif 140 <= primary_channel <= 144:
                return (138, 146)
            elif 149 <= primary_channel <= 153:
                return (147, 155)
            elif 157 <= primary_channel <= 161:
                return (155, 163)
            elif 165 <= primary_channel <= 169:
                return (163, 171)
            elif 173 <= primary_channel <= 177:
                return (171, 179)

        elif width_mhz == 80:
            # 80 MHz blocks
            if 36 <= primary_channel <= 48:
                return (34, 50)
            elif 52 <= primary_channel <= 64:
                return (50, 66)
            elif 100 <= primary_channel <= 112:
                return (98, 114)
            elif 116 <= primary_channel <= 128:
                return (114, 130)
            elif 132 <= primary_channel <= 144:
                return (130, 146)
            elif 149 <= primary_channel <= 161:
                return (147, 163)
            elif 165 <= primary_channel <= 177:
                return (163, 179)

        elif width_mhz == 160:
            # 160 MHz blocks
            if 36 <= primary_channel <= 64:
                return (34, 66)
            elif 100 <= primary_channel <= 128:
                return (98, 130)
            # no 160 MHz block between 132-144
            elif 149 <= primary_channel <= 177:
                return (147, 179)

    # Fallback to simple spanning
    half = channel_half_span_for_width(width_mhz)
    return (primary_channel - half, primary_channel + half)


class SpanDirection(StrEnum):
    UPPER = "upper"
    LOWER = "lower"


@dataclass
class _Chan:
    channel_band: int
    channel_number: int
    channel_width: int
    span_direction: SpanDirection | None = None


@dataclass
class _Net:
    ssid: str
    bssid: str
    rssi: int
    channel: _Chan


def to_series(nws: List[_Net]) -> List[dict]:
    """Convert networks to ApexCharts series data with correct spans.

    Expects items resembling PyNetwork:
      - .ssid: str
      _ .bssid: str
      - .rssi: int
      - .channel.channel_band: int
      - .channel.channel_number: int
      - .channel.channel_width: int (MHz)
    """
    series = []
    for nw in nws:
        try:
            band = nw.channel.channel_band
            reported_channel = int(nw.channel.channel_number)
            width_mhz = int(nw.channel.channel_width)
            span_direction = nw.channel.span_direction

            left, right = get_channel_block(
                reported_channel, width_mhz, band, span_direction
            )

            middle = (left + right) / 2

            series.append(
                {
                    # "name": nw.ssid,
                    # "bssid": nw.bssid,
                    "name": nw.bssid,
                    "ssid": nw.ssid,
                    "channel": reported_channel,  # Store primary channel for labeling
                    "data": [[left, -100], [middle, int(nw.rssi)], [right, -100]],
                }
            )
        except Exception:
            # Skip malformed entries defensively
            continue
    return series
