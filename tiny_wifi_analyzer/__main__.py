import json
import logging
import os.path
import queue
import threading
from time import sleep

import AppKit
import CoreLocation
import CoreWLAN
import Foundation
import webview

# NOTE: https://github.com/r0x0r/pywebview/issues/496
from objc import nil, registerMetaDataForSelector  # pylint: disable=unused-import # noqa F401

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

CHANNEL_BAND_24 = 1
CHANNEL_BAND_5 = 2
CHANNEL_NUMBER_MAX_24 = 16
CHANNEL_NUMBER_MAX_5 = 170

update_queue = queue.Queue()
is_closing = False

debug_scan_count = 0

webview.settings["ALLOW_DOWNLOADS"] = True

class PyChannel:
    def __init__(self, channel):
        self.channel_band = channel.channelBand()
        self.channel_number = channel.channelNumber()
        self.channel_width = channel.channelWidth()

    def __repr__(self):
        return (
            "<CWChannel> [channel_band={}, channel_number={}, channel_width={}]".format(
                self.channel_band, self.channel_number, self.channel_width
            )
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
    sleep(5)


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
        window.evaluate_js("window.chart24.updateSeries({})".format(series_json24))

        nws5 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_5, nws)
        nws5 = sorted(nws5, key=lambda x: x.channel.channel_number)
        series5 = to_series(nws5)
        series_json5 = json.dumps(series5)
        window.evaluate_js("window.chart5.updateSeries({})".format(series_json5))
    except queue.Empty:
        if thread is None or not thread.is_alive():
            thread = threading.Thread(target=worker_wait)
            thread.daemon = True
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


class LocationManagerDelegate(AppKit.NSObject):
    def locationManagerDidChangeAuthorization_(self, manager):
        status = manager.authorizationStatus()
        if status in [
            CoreLocation.kCLAuthorizationStatusDenied,
            CoreLocation.kCLAuthorizationStatusNotDetermined,
        ]:
            self.show_dialog()

    def show_dialog(self):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Location Services are disabled")
        alert.setInformativeText_(
            "On macOS 14 Sonoma and Later, Location Services permission is required to get Wi-Fi SSIDs.\n"
            + "Please enable Location Services in System Preferences > Security & Privacy > Privacy > Location Services."
        )
        alert.addButtonWithTitle_("Open Preferences")
        alert.addButtonWithTitle_("OK")
        response = alert.runModal()
        if response == AppKit.NSAlertFirstButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                Foundation.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices"
                )
            )
        AppKit.NSApplication.sharedApplication().terminate_(None)


def request_location_permission():
    location_manager = CoreLocation.CLLocationManager.alloc().init().retain()
    delegate = LocationManagerDelegate.alloc().init().retain()
    location_manager.setDelegate_(delegate)
    # location_manager.delegate()
    # location_manager.startUpdatingLocation()
    location_manager.requestWhenInUseAuthorization()
    for i in range(100):
        status = location_manager.authorizationStatus()
        if not status == 0:
            break
        sleep(0.01)


def main():
    # NOTE: Sonoma (macOS 11) and later requires location permission to read Wi-Fi SSIDs.
    os_version = AppKit.NSAppKitVersionNumber
    # print(os_version, AppKit.NSAppKitVersionNumber13_1)
    if os_version > AppKit.NSAppKitVersionNumber13_1:
        request_location_permission()

    # Bring the app to the foreground
    AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    index_html = os.path.join(os.path.dirname(__file__), "view/index.html")
    window = webview.create_window("Tiny Wi-Fi Analyzer", index_html)
    window.events.closing += on_closing
    webview.start(startup, window, debug=True)


if __name__ == "__main__":
    main()
