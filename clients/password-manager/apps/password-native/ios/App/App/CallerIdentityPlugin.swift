import Foundation
import UIKit
import Capacitor

@objc(CallerIdentityPlugin)
public class CallerIdentityPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "CallerIdentityPlugin"
    public let jsName = "CallerIdentity"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getLastCaller", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openUrlInPackage", returnType: CAPPluginReturnPromise)
    ]

    @objc func getLastCaller(_ call: CAPPluginCall) {
        let snap = CallerIdentityStore.load()
        let pkg = snap?["packageName"] as? String ?? ""
        call.resolve([
            "packageName": pkg,
            "appLabel": "",
            "sha256CertFingerprints": [] as [String],
            "handlesCallback": true
        ])
    }

    @objc func openUrlInPackage(_ call: CAPPluginCall) {
        guard let urlStr = call.getString("url"), let url = URL(string: urlStr) else {
            call.reject("url required")
            return
        }
        DispatchQueue.main.async {
            UIApplication.shared.open(url, options: [:]) { ok in
                if ok {
                    call.resolve()
                } else {
                    call.reject("open failed")
                }
            }
        }
    }
}
