# Security policy / 安全说明

## Never publish runtime secrets

Do not put any of the following in a commit, Issue, Discussion, screenshot or
log attachment:

- Xiaomi `passToken`, service tokens, device IDs, MAC/SSID or signed OTA URLs;
- Codex, Claude Code or Kimi session/OAuth data;
- DeepSeek API keys;
- real LAN addresses, generated quota JSON/images, patched firmware or loader
  manifests made from a user's firmware.

The reviewed workflow stores provider credentials only in their official local
stores or macOS Keychain. Signed OTA tickets and quota artifacts are runtime
files with mode 0600 and are ignored by Git.

If a credential or signed URL is exposed, revoke or rotate it first. Deleting
a GitHub file or editing an Issue is not sufficient because copies and Git
history may remain.

## Reporting a vulnerability

Use GitHub's private **Report a vulnerability** action when it is available.
Otherwise open a public Issue containing only a short, non-sensitive summary
and ask the maintainer for a private contact channel. Never include a proof of
concept that contains a live credential, device identifier or signed URL.

## 不要公开运行时秘密

不要把米家 Token、设备标识、签名 OTA URL、AI 服务登录态/API Key、真实局域网
地址、额度产物或由用户固件生成的 BIN 放进 Commit、Issue、Discussion、截图或日志
附件。若已经泄露，先撤销或轮换凭据；仅删除网页内容不能清除既有副本和 Git 历史。

报告漏洞时优先使用 GitHub 的私密 **Report a vulnerability**。若仓库没有开启该
入口，只提交不含敏感细节的简短 Issue，请维护者提供私下沟通方式。
