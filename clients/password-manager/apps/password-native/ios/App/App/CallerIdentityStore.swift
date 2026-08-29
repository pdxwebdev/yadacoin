import Foundation

enum CallerIdentityStore {
    static let defaultsKey = "yada_caller_identity"

    static func save(bundleId: String?, url: String?) {
        var dict: [String: Any] = [
            "timestampMs": Int64(Date().timeIntervalSince1970 * 1000)
        ]
        if let bundleId, !bundleId.isEmpty {
            dict["packageName"] = bundleId
        }
        if let url, !url.isEmpty {
            dict["url"] = url
        }
        UserDefaults.standard.set(dict, forKey: defaultsKey)
    }

    static func load() -> [String: Any]? {
        UserDefaults.standard.dictionary(forKey: defaultsKey)
    }
}
