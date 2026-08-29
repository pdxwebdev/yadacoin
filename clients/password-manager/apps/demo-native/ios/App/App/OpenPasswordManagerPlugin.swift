import Foundation
import UIKit
import Capacitor

@objc(OpenPasswordManagerPlugin)
public class OpenPasswordManagerPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "OpenPasswordManagerPlugin"
    public let jsName = "OpenPasswordManager"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "open", returnType: CAPPluginReturnPromise)
    ]

    @objc func open(_ call: CAPPluginCall) {
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
