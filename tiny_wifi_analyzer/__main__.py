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

from tiny_wifi_analyzer.series import (
    CHANNEL_BAND_24,
    CHANNEL_BAND_5,
    CHANNEL_BAND_6,
    CHANNEL_NUMBER_MAX_24,
    CHANNEL_NUMBER_MAX_5,
    CHANNEL_NUMBER_MAX_6,
    to_series as series_from_networks,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

update_queue = queue.Queue()
is_closing = False
scanner_thread = None
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


def get_supported_bands():
    client = CoreWLAN.CWWiFiClient.alloc().init()
    iface_default = client.interface()
    channels = iface_default.supportedWLANChannels()

    supported_bands = {"24": False, "5": False, "6": False}

    for channel in channels:
        band = channel.channelBand()
        if band == CHANNEL_BAND_24:
            supported_bands["24"] = True
        elif band == CHANNEL_BAND_5:
            supported_bands["5"] = True
        elif band == CHANNEL_BAND_6:
            supported_bands["6"] = True

    return supported_bands


def start_scanner(interval_ms: int) -> threading.Thread:
    def loop():
        while not is_closing:
            try:
                name, nws = scan()
                update_queue.put((name, nws))
                # # track and optionally log scan count
                # global debug_scan_count
                # debug_scan_count += 1
                # logger.debug(
                #     "debug_scan_count=%d networks=%d", debug_scan_count, len(nws)
                # )
            except Exception as e:  # pragma: no cover - platform specific
                logger.warning("scan failed: %s", e)
            # sleep for interval
            sleep(max(0.05, interval_ms / 1000.0))

    t = threading.Thread(target=loop, name="scanner", daemon=True)
    t.start()
    return t


def to_series(nws):
    # Delegate to pure implementation that maps MHz widths to channel steps
    return series_from_networks(nws)


def update(window, supported_bands):
    if is_closing:
        return

    try:
        # If there are multiple queued updates, take the most recent snapshot
        name, nws = update_queue.get_nowait()
        while True:
            try:
                name, nws = update_queue.get_nowait()
            except queue.Empty:
                break

        window.set_title(name)

        if supported_bands["24"]:
            nws24 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_24, nws)
            nws24 = sorted(nws24, key=lambda x: x.channel.channel_number)
            series24 = to_series(nws24)
            series_json24 = json.dumps(series24)
            # window.evaluate_js("window.chart24.updateSeries({})".format(series_json24))
            window.evaluate_js(
                "window.updateChart('{}',{})".format("24", series_json24)
            )

        if supported_bands["5"]:
            nws5 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_5, nws)
            nws5 = sorted(nws5, key=lambda x: x.channel.channel_number)
            series5 = to_series(nws5)
            series_json5 = json.dumps(series5)
            # window.evaluate_js("window.chart5.updateSeries({})".format(series_json5))
            window.evaluate_js("window.updateChart('{}',{})".format("5", series_json5))

        if supported_bands["6"]:
            nws6 = filter(lambda x: x.channel.channel_band == CHANNEL_BAND_6, nws)
            nws6 = sorted(nws6, key=lambda x: x.channel.channel_number)
            series6 = to_series(nws6)
            series_json6 = json.dumps(series6)
            # window.evaluate_js("window.chart6.updateSeries({})".format(series_json6))
            window.evaluate_js("window.updateChart('{}',{})".format("6", series_json6))

    except queue.Empty:
        # nothing to do this tick
        pass


def setup_client(window):
    supported_bands = get_supported_bands()
    window.evaluate_js("window.init({})".format(json.dumps(supported_bands)))


def startup(window):
    # configure and start background scanner (fixed interval)
    interval_ms = 3000
    global scanner_thread
    if scanner_thread is None:
        scanner_thread = start_scanner(interval_ms)

    supported_bands = get_supported_bands()
    # UI update loop
    while not is_closing:
        update(window, supported_bands)
        sleep(0.3)


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
        alert.addButtonWithTitle_("Ignore")
        alert.addButtonWithTitle_("Quit")
        response = alert.runModal()
        if response == AppKit.NSAlertFirstButtonReturn:
            AppKit.NSWorkspace.sharedWorkspace().openURL_(
                Foundation.NSURL.URLWithString_(
                    "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices"
                )
            )
        elif response == AppKit.NSAlertSecondButtonReturn:
            pass
        else:
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
    # Default logging level
    logging.basicConfig(level=logging.WARNING)

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
    window.events.loaded += setup_client
    webview.start(startup, window, debug=True)


if __name__ == "__main__":
    main()
