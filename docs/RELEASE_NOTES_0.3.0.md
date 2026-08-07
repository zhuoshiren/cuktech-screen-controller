# CUKTECH Screen Controller 0.3.0

> Safety correction: the historical `download-only` UI below has been
> replaced by host-side CDN readback because AP01 1.0.2_0031 may continue into
> installation after a download-only request.

## 中文

### Windows 图形软件

- 新增 Windows 10/11 x64 版 CUKTECH Screen Controller；
- 提供与 macOS 版一致的实时预览、自定义图片/GIF、三种适配方式、Bridge
  状态、运行日志、登录自动启动和系统托盘；
- 新增 Windows 新手引导与只读准备检查；
- 支持从已登录的 Claude Desktop 和 Codex 获取 5 小时、本周与 Fable 5 额度；
- Windows Claude 登录态使用当前用户 DPAPI 在内存中解密，不写入画面或 JSON；
- 新增 BFNP/SHA-256 预检、米家凭据 JSON、FDS 票据生成/导入与
  `download-only` 验证界面；
- Release 提供免 Python 的自包含 ZIP 与双击安装器。

### 跨平台与工程改进

- Codex JSON-RPC 管道读取不再依赖 POSIX `select`，可在 Windows 工作；
- 增加 Windows Chromium Cookie、批处理 Codex 路径和米家本机 JSON 支持；
- 新增 Windows Runtime 单元测试、PyInstaller 构建和 Windows Release 工作流；
- 更新中英文 README、Windows 教程、零基础教程、准备清单和 Coding Agent Skill；
- 日常画面仍只写 AP01 的 `/tmp` RAM 槽位，不会随 5 分钟刷新反复写 Flash。

### 下载

- Windows 10/11 x64：`CUKTECH-Screen-Controller-0.3.0-Windows-x64.zip`
- Apple Silicon macOS 14+：`CUKTECH-Screen-Controller-v0.3.0-macOS-arm64.zip`

## English

### Windows desktop app

- Adds CUKTECH Screen Controller for 64-bit Windows 10 and 11.
- Matches the macOS workflow with preview, artwork/GIF push, three fit modes,
  Bridge health, logs, login startup and a system tray.
- Reads signed-in Claude Desktop and Codex quota windows locally. Claude's
  Windows Electron cookies are decrypted in memory with current-user DPAPI.
- Adds onboarding, BFNP/SHA-256 preflight, local Mi Home credential JSON,
  FDS ticket handoff and download-only validation.
- Ships as a self-contained ZIP with a double-click installer; no separate
  Python installation is required.

### Cross-platform improvements

- Makes Codex JSON-RPC pipe reading Windows-compatible.
- Adds Windows Chromium cookie, Codex batch-shim and Mi Home JSON support.
- Adds Windows runtime tests, PyInstaller packaging and release CI.
- Updates bilingual documentation and the coding-agent Skill.
- Normal five-minute screen updates still use AP01's RAM-backed `/tmp` slots,
  not repeated firmware Flash writes.
