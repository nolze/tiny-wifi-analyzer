import tiny_wifi_analyzer.series as series


def make_net(ssid: str, bssid: str, rssi: int, band: int, ch: int, width: int):
    ch_obj = series._Chan(channel_band=band, channel_number=ch, channel_width=width)
    return series._Net(ssid=ssid, bssid=bssid, rssi=rssi, channel=ch_obj)


def test_channel_half_span_for_width():
    assert series.channel_half_span_for_width(20) == 2
    assert series.channel_half_span_for_width(40) == 4
    assert series.channel_half_span_for_width(80) == 8
    assert series.channel_half_span_for_width(160) == 16
    # fallback/default
    assert series.channel_half_span_for_width(None) == 2


def test_to_series_24ghz_basic_triangle():
    nw = make_net("Test", "ff:ff:ff:ff", -50, series.CHANNEL_BAND_24, 6, 20)
    s = series.to_series([nw])
    assert len(s) == 1
    name = s[0]["name"]
    pts = s[0]["data"]
    assert name == "ff:ff:ff:ff"
    # left, apex, right
    assert pts[0] == [4, -100]
    assert pts[1] == [6, -50]
    assert pts[2] == [8, -100]


def test_to_series_24ghz_clamped():
    nw = make_net("Edge", "ff:ff:ff:ff", -40, series.CHANNEL_BAND_24, 1, 40)
    s = series.to_series([nw])
    pts = s[0]["data"]
    # 40 MHz => half span 4, but left clamps to 1
    assert pts[0][0] == 1
    assert pts[1][0] == 1
    assert pts[2][0] == 5


def test_to_series_5ghz_width_mapping():
    nw = make_net("W80", "ff:ff:ff:ff", -60, series.CHANNEL_BAND_5, 100, 80)
    s = series.to_series([nw])
    pts = s[0]["data"]
    # 80 MHz => half span 8
    assert pts[0] == [92, -100]
    assert pts[1] == [100, -60]
    assert pts[2] == [108, -100]


def test_to_series_6ghz_clamped_right():
    nw = make_net("Big", "ff:ff:ff:ff", -55, series.CHANNEL_BAND_6, 230, 160)
    s = series.to_series([nw])
    pts = s[0]["data"]
    # 160 MHz => half 16; right clamps to max (233)
    assert pts[0][0] == 214
    assert pts[1][0] == 230
    assert pts[2][0] == 233
