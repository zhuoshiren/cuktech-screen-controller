# CUKTECH Screen Controller 0.5.0

## 中文

### 真机验证双页面

- 新增 AP2B 双页传输：Codex + Claude Code、Kimi Code + DeepSeek；
- 固定使用虚拟形象 `window 7` 与原天气 `window 5`，保留设置、日历、时间和电源；
- 通过单活动 GIF 解码器和 1×1 tmpfs 占位图解决多解码器白屏；
- 旋钮切页时按需交换解码源并重新居中，持续在 RAM 中刷新；
- 只重置运行时空闲计数器，不修改持久化屏幕设置。

### 账号与安全

- Codex 使用官方本机 `app-server`；
- Claude Code 只缓存官方 `statusLine.rate_limits` 的清洗字段；
- Kimi Code 使用官方本机 OAuth 与用量接口，并显示 Allegro 套餐；
- DeepSeek API Key 使用 macOS 钥匙串，输出不包含密钥或 Session；
- LAN 内容端点使用 AP01 私有 IPv4 allow-list；额度 JSON 仅允许本机访问。
- 额度 JSON、图片与 AP2B 运行时文件统一设为 0600；持久日志不记录客户端 IP；
- 米家 PassToken 通过 stdin 交给 Keychain Helper，不再出现在进程参数；
- 签名 OTA URL 只写入原子创建的 0600 票据文件，网络异常不保留完整 URL；
- GitHub Skill 不启用旧版 Claude Desktop Cookie 采集路径。

### OTA 安全修正

- 禁用 AP01 设备端 `--download-only`，因为 1.0.2_0031 实测可能继续自动安装；
- 新增 `--verify-download`：由电脑从官方 OTA CDN 回读完整镜像，核对 BFNP、
  大小、SHA-256 和 MD5，不创建米家会话、不连接 AP01；
- 保留独立的最终安装确认；日常页面更新继续只写 tmpfs RAM。

## English

- Adds the real-device-tested AP2B two-page layout for Codex/Claude Code and
  Kimi Code/DeepSeek.
- Reuses physical window 7, replaces Weather window 5, and keeps one full-size
  GIF decoder active to avoid white pages.
- Uses official local/API sources with a sanitized Claude Code statusLine
  cache, macOS Keychain for DeepSeek, an AP01 client allow-list and
  localhost-only balance JSON.
- Keeps quota artifacts and OTA tickets private, removes secrets and LAN
  addresses from process arguments/logs, and excludes the legacy Claude
  Desktop cookie collector from the recommended Skill workflow.
- Disables unsafe device `download-only`; host-side `--verify-download` now
  compares the complete official CDN object without contacting AP01.
