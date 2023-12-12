cordova.define('cordova/plugin_list', function(require, exports, module) {
module.exports = [
    {
        "file": "plugins/cordova-plugin-qrscanner/www/www.min.js",
        "id": "cordova-plugin-qrscanner.QRScanner",
        "clobbers": [
            "QRScanner"
        ]
    },
    {
        "file": "plugins/cordova-plugin-qrscanner/src/browser/plugin.min.js",
        "id": "cordova-plugin-qrscanner.QRScannerProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-device/www/device.js",
        "id": "cordova-plugin-device.device",
        "clobbers": [
            "device"
        ]
    },
    {
        "file": "plugins/cordova-plugin-device/src/browser/DeviceProxy.js",
        "id": "cordova-plugin-device.DeviceProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-statusbar/www/statusbar.js",
        "id": "cordova-plugin-statusbar.statusbar",
        "clobbers": [
            "window.StatusBar"
        ]
    },
    {
        "file": "plugins/cordova-plugin-statusbar/src/browser/StatusBarProxy.js",
        "id": "cordova-plugin-statusbar.StatusBarProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/lodash.js",
        "id": "cordova-plugin-advanced-http.lodash"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/umd-tough-cookie.js",
        "id": "cordova-plugin-advanced-http.tough-cookie"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/messages.js",
        "id": "cordova-plugin-advanced-http.messages"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/local-storage-store.js",
        "id": "cordova-plugin-advanced-http.local-storage-store"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/cookie-handler.js",
        "id": "cordova-plugin-advanced-http.cookie-handler"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/angular-integration.js",
        "id": "cordova-plugin-advanced-http.angular-integration"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/helpers.js",
        "id": "cordova-plugin-advanced-http.helpers"
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/www/advanced-http.js",
        "id": "cordova-plugin-advanced-http.http",
        "clobbers": [
            "cordova.plugin.http"
        ]
    },
    {
        "file": "plugins/cordova-plugin-advanced-http/src/browser/cordova-http-plugin.js",
        "id": "cordova-plugin-advanced-http.http-proxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-camera/www/CameraConstants.js",
        "id": "cordova-plugin-camera.Camera",
        "clobbers": [
            "Camera"
        ]
    },
    {
        "file": "plugins/cordova-plugin-camera/www/CameraPopoverOptions.js",
        "id": "cordova-plugin-camera.CameraPopoverOptions",
        "clobbers": [
            "CameraPopoverOptions"
        ]
    },
    {
        "file": "plugins/cordova-plugin-camera/www/Camera.js",
        "id": "cordova-plugin-camera.camera",
        "clobbers": [
            "navigator.camera"
        ]
    },
    {
        "file": "plugins/cordova-plugin-camera/src/browser/CameraProxy.js",
        "id": "cordova-plugin-camera.CameraProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-clipboard/www/clipboard.js",
        "id": "cordova-clipboard.Clipboard",
        "clobbers": [
            "cordova.plugins.clipboard"
        ]
    },
    {
        "file": "plugins/cordova-plugin-x-socialsharing/www/SocialSharing.js",
        "id": "cordova-plugin-x-socialsharing.SocialSharing",
        "clobbers": [
            "window.plugins.socialsharing"
        ]
    },
    {
        "file": "plugins/cordova-plugin-badge/www/badge.js",
        "id": "cordova-plugin-badge.Badge",
        "clobbers": [
            "cordova.plugins.notification.badge"
        ]
    },
    {
        "file": "plugins/cordova-plugin-badge/src/browser/favico.min.js",
        "id": "cordova-plugin-badge.Badge.Favico",
        "clobbers": [
            "cordova.plugins.notification.badge.Favico"
        ]
    },
    {
        "file": "plugins/cordova-plugin-badge/src/browser/BadgeProxy.js",
        "id": "cordova-plugin-badge.Badge.Proxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-keyboard/www/keyboard.js",
        "id": "cordova-plugin-keyboard.keyboard",
        "clobbers": [
            "window.Keyboard"
        ]
    },
    {
        "file": "plugins/cordova-plugin-splashscreen/www/splashscreen.js",
        "id": "cordova-plugin-splashscreen.SplashScreen",
        "clobbers": [
            "navigator.splashscreen"
        ]
    },
    {
        "file": "plugins/cordova-plugin-splashscreen/src/browser/SplashScreenProxy.js",
        "id": "cordova-plugin-splashscreen.SplashScreenProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-mixpanel/www/mixpanel.js",
        "id": "cordova-plugin-mixpanel.Mixpanel",
        "clobbers": [
            "mixpanel"
        ]
    },
    {
        "file": "plugins/cordova-plugin-mixpanel/src/browser/MixpanelProxy.js",
        "id": "cordova-plugin-mixpanel.MixpanelProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-sqlite-storage/www/SQLitePlugin.js",
        "id": "cordova-sqlite-storage.SQLitePlugin",
        "clobbers": [
            "SQLitePlugin"
        ]
    },
    {
        "file": "plugins/ionic-plugin-deeplinks/www/deeplink.js",
        "id": "ionic-plugin-deeplinks.deeplink",
        "clobbers": [
            "IonicDeeplink"
        ],
        "runs": true
    },
    {
        "file": "plugins/ionic-plugin-deeplinks/src/browser/DeeplinkProxy.js",
        "id": "ionic-plugin-deeplinks.IonicDeeplinkProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Promise.js",
        "id": "cordova-plugin-googlemaps.Promise"
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/BaseClass.js",
        "id": "cordova-plugin-googlemaps.BaseClass",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/BaseArrayClass.js",
        "id": "cordova-plugin-googlemaps.BaseArrayClass",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/LatLng.js",
        "id": "cordova-plugin-googlemaps.LatLng",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/LatLngBounds.js",
        "id": "cordova-plugin-googlemaps.LatLngBounds",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/VisibleRegion.js",
        "id": "cordova-plugin-googlemaps.VisibleRegion",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Location.js",
        "id": "cordova-plugin-googlemaps.Location",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/CameraPosition.js",
        "id": "cordova-plugin-googlemaps.CameraPosition",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Polyline.js",
        "id": "cordova-plugin-googlemaps.Polyline",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Polygon.js",
        "id": "cordova-plugin-googlemaps.Polygon",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Marker.js",
        "id": "cordova-plugin-googlemaps.Marker",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/HtmlInfoWindow.js",
        "id": "cordova-plugin-googlemaps.HtmlInfoWindow",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Circle.js",
        "id": "cordova-plugin-googlemaps.Circle",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/TileOverlay.js",
        "id": "cordova-plugin-googlemaps.TileOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/GroundOverlay.js",
        "id": "cordova-plugin-googlemaps.GroundOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Common.js",
        "id": "cordova-plugin-googlemaps.Common",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/encoding.js",
        "id": "cordova-plugin-googlemaps.encoding",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/spherical.js",
        "id": "cordova-plugin-googlemaps.spherical",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/poly.js",
        "id": "cordova-plugin-googlemaps.poly",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Geocoder.js",
        "id": "cordova-plugin-googlemaps.Geocoder",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/LocationService.js",
        "id": "cordova-plugin-googlemaps.LocationService",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Map.js",
        "id": "cordova-plugin-googlemaps.Map",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/event.js",
        "id": "cordova-plugin-googlemaps.event",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/MapTypeId.js",
        "id": "cordova-plugin-googlemaps.MapTypeId",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/KmlOverlay.js",
        "id": "cordova-plugin-googlemaps.KmlOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/KmlLoader.js",
        "id": "cordova-plugin-googlemaps.KmlLoader",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Environment.js",
        "id": "cordova-plugin-googlemaps.Environment",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/MarkerCluster.js",
        "id": "cordova-plugin-googlemaps.MarkerCluster",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Cluster.js",
        "id": "cordova-plugin-googlemaps.Cluster",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/geomodel.js",
        "id": "cordova-plugin-googlemaps.geomodel",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/commandQueueExecutor.js",
        "id": "cordova-plugin-googlemaps.commandQueueExecutor",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/pluginInit.js",
        "id": "cordova-plugin-googlemaps.pluginInit",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/StreetViewPanorama.js",
        "id": "cordova-plugin-googlemaps.StreetViewPanorama",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Overlay.js",
        "id": "cordova-plugin-googlemaps.Overlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/Thread.js",
        "id": "cordova-plugin-googlemaps.Thread",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/InlineWorker.js",
        "id": "cordova-plugin-googlemaps.InlineWorker",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/plugin-loader-for-browser.js",
        "id": "cordova-plugin-googlemaps.googlemaps-cdv-plugin",
        "clobbers": [
            "plugin.google.maps"
        ]
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/www/js_CordovaGoogleMaps-for-browser.js",
        "id": "cordova-plugin-googlemaps.js_CordovaGoogleMaps",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/CordovaGoogleMaps.js",
        "id": "cordova-plugin-googlemaps.CordovaGoogleMaps",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginMap.js",
        "id": "cordova-plugin-googlemaps.PluginMap",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginMarker.js",
        "id": "cordova-plugin-googlemaps.PluginMarker",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginCircle.js",
        "id": "cordova-plugin-googlemaps.PluginCircle",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginGroundOverlay.js",
        "id": "cordova-plugin-googlemaps.PluginGroundOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginKmlOverlay.js",
        "id": "cordova-plugin-googlemaps.PluginKmlOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginMarkerCluster.js",
        "id": "cordova-plugin-googlemaps.PluginMarkerCluster",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginPolygon.js",
        "id": "cordova-plugin-googlemaps.PluginPolygon",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginPolyline.js",
        "id": "cordova-plugin-googlemaps.PluginPolyline",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginStreetViewPanorama.js",
        "id": "cordova-plugin-googlemaps.PluginStreetViewPanorama",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginTileOverlay.js",
        "id": "cordova-plugin-googlemaps.PluginTileOverlay",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginLocationService.js",
        "id": "cordova-plugin-googlemaps.PluginLocationService",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginGeocoder.js",
        "id": "cordova-plugin-googlemaps.PluginGeocoder",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-googlemaps/src/browser/PluginEnvironment.js",
        "id": "cordova-plugin-googlemaps.PluginEnvironment",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-file/www/DirectoryEntry.js",
        "id": "cordova-plugin-file.DirectoryEntry",
        "clobbers": [
            "window.DirectoryEntry"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/DirectoryReader.js",
        "id": "cordova-plugin-file.DirectoryReader",
        "clobbers": [
            "window.DirectoryReader"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/Entry.js",
        "id": "cordova-plugin-file.Entry",
        "clobbers": [
            "window.Entry"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/File.js",
        "id": "cordova-plugin-file.File",
        "clobbers": [
            "window.File"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileEntry.js",
        "id": "cordova-plugin-file.FileEntry",
        "clobbers": [
            "window.FileEntry"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileError.js",
        "id": "cordova-plugin-file.FileError",
        "clobbers": [
            "window.FileError"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileReader.js",
        "id": "cordova-plugin-file.FileReader",
        "clobbers": [
            "window.FileReader"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileSystem.js",
        "id": "cordova-plugin-file.FileSystem",
        "clobbers": [
            "window.FileSystem"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileUploadOptions.js",
        "id": "cordova-plugin-file.FileUploadOptions",
        "clobbers": [
            "window.FileUploadOptions"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileUploadResult.js",
        "id": "cordova-plugin-file.FileUploadResult",
        "clobbers": [
            "window.FileUploadResult"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/FileWriter.js",
        "id": "cordova-plugin-file.FileWriter",
        "clobbers": [
            "window.FileWriter"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/Flags.js",
        "id": "cordova-plugin-file.Flags",
        "clobbers": [
            "window.Flags"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/LocalFileSystem.js",
        "id": "cordova-plugin-file.LocalFileSystem",
        "clobbers": [
            "window.LocalFileSystem"
        ],
        "merges": [
            "window"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/Metadata.js",
        "id": "cordova-plugin-file.Metadata",
        "clobbers": [
            "window.Metadata"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/ProgressEvent.js",
        "id": "cordova-plugin-file.ProgressEvent",
        "clobbers": [
            "window.ProgressEvent"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/fileSystems.js",
        "id": "cordova-plugin-file.fileSystems"
    },
    {
        "file": "plugins/cordova-plugin-file/www/requestFileSystem.js",
        "id": "cordova-plugin-file.requestFileSystem",
        "clobbers": [
            "window.requestFileSystem"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/resolveLocalFileSystemURI.js",
        "id": "cordova-plugin-file.resolveLocalFileSystemURI",
        "merges": [
            "window"
        ]
    },
    {
        "file": "plugins/cordova-plugin-file/www/browser/isChrome.js",
        "id": "cordova-plugin-file.isChrome",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-file/www/browser/Preparing.js",
        "id": "cordova-plugin-file.Preparing",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-file/src/browser/FileProxy.js",
        "id": "cordova-plugin-file.browserFileProxy",
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-file/www/fileSystemPaths.js",
        "id": "cordova-plugin-file.fileSystemPaths",
        "merges": [
            "cordova"
        ],
        "runs": true
    },
    {
        "file": "plugins/cordova-plugin-file/www/browser/FileSystem.js",
        "id": "cordova-plugin-file.firefoxFileSystem",
        "merges": [
            "window.FileSystem"
        ]
    },
    {
        "file": "plugins/es6-promise-plugin/www/promise.js",
        "id": "es6-promise-plugin.Promise",
        "runs": true
    }
];
module.exports.metadata = 
// TOP OF METADATA
{
    "cordova-plugin-qrscanner": "2.6.2",
    "cordova-plugin-device": "1.1.7",
    "cordova-plugin-statusbar": "2.4.3",
    "cordova-plugin-whitelist": "1.3.4",
    "cordova-plugin-advanced-http": "1.11.1",
    "cordova-plugin-camera": "3.0.0",
    "cordova-clipboard": "1.3.0",
    "cordova-plugin-x-socialsharing": "5.6.2",
    "cordova-plugin-badge": "0.8.8",
    "cordova-plugin-keyboard": "1.2.0",
    "cordova-plugin-add-swift-support": "1.7.2",
    "cordova-plugin-splashscreen": "5.0.3",
    "cordova-plugin-mixpanel": "4.7.0",
    "cordova-sqlite-storage": "2.6.0",
    "cordova-plugin-geolocation": "4.0.2",
    "ionic-plugin-deeplinks": "1.0.20",
    "cordova-plugin-googlemaps": "2.7.1",
    "cordova-plugin-file": "6.0.2",
    "es6-promise-plugin": "4.2.2"
}
// BOTTOM OF METADATA
});