#!/usr/bin/env swift

import Darwin
import Foundation
import Security

guard CommandLine.arguments.count == 3 else {
    fputs("usage: store-mi-home-keychain SERVICE ACCOUNT\n", stderr)
    exit(2)
}

let service = CommandLine.arguments[1]
let account = CommandLine.arguments[2]
let secretData = FileHandle.standardInput.readDataToEndOfFile()
guard !secretData.isEmpty,
      let object = try? JSONSerialization.jsonObject(with: secretData) as? [String: Any],
      object["userId"] is String,
      object["passToken"] is String else {
    fputs("invalid Mi Home credential payload\n", stderr)
    exit(3)
}

var trustedApplication: SecTrustedApplication?
guard SecTrustedApplicationCreateFromPath("/usr/bin/security", &trustedApplication) == errSecSuccess,
      let trustedApplication else {
    fputs("failed to create Keychain trusted application\n", stderr)
    exit(4)
}

var access: SecAccess?
guard SecAccessCreate(
    "CUKTECH Screen Xiaomi Session" as CFString,
    [trustedApplication] as CFArray,
    &access
) == errSecSuccess, let access else {
    fputs("failed to create Keychain access control\n", stderr)
    exit(5)
}

let lookup: [CFString: Any] = [
    kSecClass: kSecClassGenericPassword,
    kSecAttrService: service,
    kSecAttrAccount: account,
]
let changes: [CFString: Any] = [
    kSecValueData: secretData,
    kSecAttrAccess: access,
]

var status = SecItemUpdate(lookup as CFDictionary, changes as CFDictionary)
if status == errSecItemNotFound {
    var newItem = lookup
    newItem[kSecValueData] = secretData
    newItem[kSecAttrAccess] = access
    status = SecItemAdd(newItem as CFDictionary, nil)
}
guard status == errSecSuccess else {
    fputs("failed to store Mi Home session in Keychain\n", stderr)
    exit(6)
}
