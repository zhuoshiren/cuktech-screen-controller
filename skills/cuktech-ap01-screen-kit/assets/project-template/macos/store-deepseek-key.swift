#!/usr/bin/env swift

import AppKit
import Darwin
import Foundation
import Security

private let service = "com.wqytommy.CUKTECHScreenController.deepseek-api-key"
private let account = "api"

private func showMessage(_ title: String, _ detail: String, style: NSAlert.Style) {
    let alert = NSAlert()
    alert.messageText = title
    alert.informativeText = detail
    alert.alertStyle = style
    alert.addButton(withTitle: "好")
    alert.runModal()
}

let stdinMode = CommandLine.arguments.contains("--stdin")
var secret: String
if stdinMode {
    guard let raw = readLine(strippingNewline: true) else {
        exit(2)
    }
    secret = raw.trimmingCharacters(in: .whitespacesAndNewlines)
} else {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    app.activate(ignoringOtherApps: true)

    let input = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 430, height: 26))
    input.placeholderString = "粘贴 DeepSeek API Key（输入内容不会显示）"

    let prompt = NSAlert()
    prompt.messageText = "保存 DeepSeek API Key"
    prompt.informativeText = "密钥只会直接写入 macOS 登录钥匙串，不会输出到终端、日志或项目文件。"
    prompt.alertStyle = .informational
    prompt.accessoryView = input
    prompt.addButton(withTitle: "安全保存")
    prompt.addButton(withTitle: "取消")
    prompt.window.initialFirstResponder = input

    guard prompt.runModal() == .alertFirstButtonReturn else {
        exit(2)
    }
    secret = input.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
}
guard secret.hasPrefix("sk-"), secret.count >= 20 else {
    showMessage("密钥格式不正确", "请输入 DeepSeek 平台生成、以 sk- 开头的 API Key。", style: .warning)
    exit(3)
}
guard let secretData = secret.data(using: .utf8) else {
    exit(4)
}

// Trust only the macOS `security` tool used by the background bridge to read
// this item.  The secret itself never appears in that tool's command line.
var trustedApplication: SecTrustedApplication?
let trustStatus = SecTrustedApplicationCreateFromPath("/usr/bin/security", &trustedApplication)
guard trustStatus == errSecSuccess, let trustedApplication else {
    secret = ""
    showMessage("无法配置钥匙串权限", "macOS 无法为屏幕服务授予只读访问。未保存密钥。", style: .critical)
    exit(5)
}

var access: SecAccess?
let accessStatus = SecAccessCreate(
    "CUKTECH Screen DeepSeek API Key" as CFString,
    [trustedApplication] as CFArray,
    &access
)
guard accessStatus == errSecSuccess, let access else {
    secret = ""
    showMessage("无法创建钥匙串项目", "未保存密钥。", style: .critical)
    exit(6)
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
secret = ""

guard status == errSecSuccess else {
    let reason = SecCopyErrorMessageString(status, nil) as String? ?? "错误码 \(status)"
    showMessage("保存失败", "钥匙串返回：\(reason)", style: .critical)
    exit(7)
}

if stdinMode {
    print("DeepSeek API Key 已安全写入 macOS 钥匙串")
} else {
    showMessage("已安全保存", "DeepSeek API Key 已写入登录钥匙串。现在可以关闭密钥页面。", style: .informational)
}
