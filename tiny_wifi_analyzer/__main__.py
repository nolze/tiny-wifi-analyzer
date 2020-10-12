import json
import logging
import os.path
import queue
import threading
from time import sleep

import CoreWLAN
import webview

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

CHANNEL_BAND_24 = 1
CHANNEL_BAND_5 = 2
CHANNEL_NUMBER_MAX_24 = 16
CHANNEL_NUMBER_MAX_5 = 170

update_queue = queue.Queue()
is_closing = False

debug_scan_count = 0


class PyChannel:
    def __init__(self, channel):
        self.channel_band = channel.channelBand()
        self.channel_number = channel.channelNumber()
        self.channel_width = channel.channelWidth()

    def __repr__(self):
        return "<CWChannel> [channel_band={}, channel_number={}, channel_width={}]".format(
            self.channel_band, self.channel_number, self.channel_width
        )


class PyNetwork:
    def __init__(self, network):
        self.ssid = network.ssid()
        self.bssid = network.bssid()
        # self.security = network.security()
        self.rssi = network.rssiValue()
        self.channel = PyChannel(network.wlanChannel())
        self.ibss = network.ibss()

    def __repr__(self):
        return "<CWNetwork> [ssid={}, bssid={}, rssi={}, channel={}, ibss={}]".format(
            self.ssid, self.bssid, self.rssi, self.channel, self.ibss
        )


def scan():
    client = CoreWLAN.CWWiFiClient.alloc().init()
    iface_default = client.interface()
    name = iface_default.interfaceName()

    nws, err = iface_default.scanForNetworksWithName_error_(None, None)
    nws = [PyNetwork(nw) for nw in nws]

    return name, nws


def worker_wait():
    def worker():
        name, nws = scan()
        update_queue.put((name, nws))

    worker()
    sleep(10)


def to_series(nws):
    return [
        {
            "name": nw.ssid,
            "data": [
                [nw.channel.channel_number - nw.channel.channel_width * 2, -100],
                [nw.channel.channel_number, nw.rssi],
                [nw.channel.channel_number + nw.channel.channel_width * 2, -100],
            ],
        }
        for nw in nws
    ]


def update(window, thread=None):
    global debug_scan_count

    if is_closing:
        return None

    logger.debug(debug_scan_count)

    try:
        name, nws = update_queue.get_nowait()
        window.set_title(name)

        nws24 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_24, nws)
        nws24 = sorted(nws24, key=lambda x: x.channel.channel_number)
        series24 = to_series(nws24)
        series_json24 = json.dumps(series24)
        window.evaluate_js("chart24.updateSeries({})".format(series_json24))

        nws5 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_5, nws)
        nws5 = sorted(nws5, key=lambda x: x.channel.channel_number)
        series5 = to_series(nws5)
        series_json5 = json.dumps(series5)
        window.evaluate_js("chart5.updateSeries({})".format(series_json5))
    except queue.Empty:
        if thread is None or not thread.is_alive():
            thread = threading.Thread(target=worker_wait)
            thread.setDaemon(True)
            thread.start()
            debug_scan_count += 1

    return thread


def startup(window):
    thread = None
    while True:
        thread = update(window, thread)
        if thread is None:
            break
        sleep(1)


def on_closing():
    global is_closing
    is_closing = True


def main():
    window = webview.create_window("Tiny Wi-Fi Analyzer", "./tiny-wifi-analyzer/view/index.html")
    window.closing += on_closing
    webview.start(startup, window, debug=True)


if __name__ == "__main__":
    main()
