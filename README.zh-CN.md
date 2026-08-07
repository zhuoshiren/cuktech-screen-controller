<div align="center">
  <img src="docs/images/cuktech-screen-controller-app.jpg" alt="CUKTECH Screen Controller macOS 软件" width="48%" />
  <img src="docs/images/windows-controller-main.png" alt="CUKTECH Screen Controller Windows 软件" width="48%" />

  # CUKTECH Screen Controller

  **酷态科 10 号电能柱 AP01 万向屏 / 万象屏自定义显示与双页面额度方案。**

  Codex + Claude Code · Kimi Code + DeepSeek · 局域网刷新 · RAM 更新

  [![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](#高级与手动配置)
  [![Toolkit](https://img.shields.io/badge/Toolkit-macOS%20%7C%20Windows-159FCB)](#平台支持)
  [![Native Apps](https://img.shields.io/badge/Native_Apps-macOS%20%7C%20Windows-0F172A)](#方法一安装图形软件)
  [![Firmware](https://img.shields.io/badge/AP01-1.0.2__0031-0F172A)](#首次配置实时固件)
  [![Screen](https://img.shields.io/badge/Screen-320%C3%97240-159FCB)](#屏幕协议)
  [![License](https://img.shields.io/badge/License-MIT-F07A32)](LICENSE)

  [平台支持](#平台支持) · [Windows 指南](docs/WINDOWS_GUIDE.zh-CN.md) · [安装前准备](docs/PREPARATION_CHECKLIST.zh-CN.md) · [零基础教程](docs/BEGINNER_GUIDE.zh-CN.md) · [安装图形软件](#方法一安装图形软件) · [交给 Coding Agent 配置](#方法二把-github-仓库交给-coding-agent)

  [English](README.md) · [简体中文](README.zh-CN.md) · [图文教程](docs/xiaohongshu-tutorial.zh-CN.md) · [Skill](#coding-agent-与-skill)
</div>

---

> [!NOTE]
> 这是
> [`wqytommy666/cuktech-screen-controller`](https://github.com/wqytommy666/cuktech-screen-controller)
> 的社区修改版 Fork，并非从零重写。仓库保留上游 Git 历史与 MIT 版权声明；
> 具体署名和本 Fork 的改动范围见 [NOTICE.md](NOTICE.md)。

## 已在真机验证：两页 Coding 额度面板

这不是概念图。下面这套方案已在 `njcuk.enstor.ap01 / 1.0.2_0031` 真机上连续
构建、刷入、修复并最终由设备所有者确认两页均正常显示。README 图片使用合成
演示数据，不包含真实余额、Token、设备地址或米家信息。

![酷态科 AP01 双页面 Codex Claude Kimi DeepSeek 额度面板](docs/images/two-page-coding-dashboard.png)

| 旋钮页面 | 显示内容 | 数据来源 |
| --- | --- | --- |
| 原虚拟形象页 `window 7` | Codex Pro + Claude Code Max | 官方 Codex `app-server`；Claude Code 官方 `statusLine` |
| 原天气页 `window 5` | Kimi Code Allegro + DeepSeek | Kimi Code 本机 OAuth；DeepSeek 官方余额 API |

实际循环顺序是：`设置 6 → Codex/Claude 7 → Kimi/DeepSeek 5 → 日历 4 → 时间 3 → 电源 0 → 设置 6`。
这个映射很关键：`window 0` 是电源，不是天气；把内容挂到错误窗口会出现“挤进设置页”
或覆盖电源页的现象。

如果你正在搜索“酷态科 AP01 万向屏刷机”“酷态科 10 号万象屏自定义界面”或
“Codex / Claude Code / Kimi Code 余额小屏”，本仓库记录的就是这套完整实现。

实现采用 **AP2B 双页包 + 单活动 GIF 解码器**。第一页复用原虚拟形象对象，第二页只
在原天气页新增一个对象；未选中的页面指向 1×1 的 `/tmp` 占位 GIF。这个设计解决了
多个 320×240 GIF 解码器同时驻留导致的白屏，同时保留原设置、日历、时间和电源页面。

完整复现、故障判断和恢复步骤见
[双页面真机案例](skills/cuktech-ap01-screen-kit/references/two-page-coding-dashboard.md)。

> [!CAUTION]
> 二进制偏移只适用于上述型号和固件。仓库不分发小米/酷态科原厂固件，也不会把
> 用户的固件、签名 OTA URL、密钥、Cookie、DID 或局域网地址提交到 GitHub。

> [!IMPORTANT]
> 已验证的双页方案不读取 Claude Desktop 或浏览器 Cookie，只接收 Claude Code
> 官方 `statusLine.rate_limits` 输入。仓库为了兼容旧版本仍保留一页版 Cookie
> 采集器，但 Skill 不会推荐或启用它。签名 OTA URL 只能通过私有票据文件传递，
> 不接受命令行明文，也不会输出到日志。

## 选择一种使用方式

CUKTECH Screen Controller 提供两种使用方式。

> **完全没有编程基础？** 直接打开[零基础使用教程](docs/BEGINNER_GUIDE.zh-CN.md)。
> 它从下载安装、macOS 第一次打开，到检查 AP01 是否收到画面逐步讲解。

> **没有米家网关也可以。** 原厂 AP01 用户只需让屏幕稳定供电、在米家中在线，
> 并让电脑与屏幕处于同一局域网。软件中的“无网关：一键获取部署包”会通过受限
> 共享服务完成 FDS 上传；真正写入前仍会要求用户明确确认。

| | 方法一：安装 macOS / Windows 软件 | 方法二：在 macOS / Windows 交给 Coding Agent |
| --- | --- | --- |
| 适合人群 | 使用原生界面的日常用户 | 首次配置、故障诊断和深度自定义 |
| 操作方式 | CUKTECH Screen Controller 图形软件 | Claude Code、Codex、OpenCode、WorkBuddy 等 |
| 自定义图片 | 选择 PNG、JPG 或 GIF 后直接推送 | 使用仓库脚本转换、验证并部署 |
| 额度面板 | 两个平台均可显示 Claude 与 Codex | macOS 可部署本页介绍的四服务双页面方案 |
| 首次加载器 | 无网关一键准备、BFNP 预检与确认安装 | 完整兼容性检查、构建和安装流程 |
| 日常刷新 | 通过 Wi-Fi 更新 AP01 内存 | 通过 Wi-Fi 更新 AP01 内存 |

## 平台支持

完整日常流程已经支持两个平台：

- **macOS：** Apple Silicon 原生 SwiftUI 软件，要求 macOS 14 或更高版本；
- **Windows：** Windows 10/11 x64 图形软件；
- 两个平台都支持画面预览、自定义图片/GIF、Claude/Codex 额度、Bridge 状态、
  登录自动启动、新手检查与无网关 OTA 部署；
- **Python 脚本与 Coding Agent 工具链**也同时支持 macOS 和 Windows，可用于
  图片转换、验证、诊断和深度自定义；
- Windows 使用 `scripts/setup-windows.ps1` 与 `scripts/diagnose-windows.ps1`，
  macOS 使用 `macos/` 目录中的脚本。

完整步骤见：[Windows 使用指南](docs/WINDOWS_GUIDE.zh-CN.md)。

## 方法一：安装图形软件

从 [GitHub Releases](https://github.com/zhuoshiren/cuktech-screen-controller/releases/latest)
下载最新版 **CUKTECH Screen Controller**：

- **Windows 10/11 x64：**解压
  `CUKTECH-Screen-Controller-0.4.1-Windows-x64.zip`，双击
  **`Install CUKTECH Screen Controller.cmd`**。详见
  [Windows 使用指南](docs/WINDOWS_GUIDE.zh-CN.md)；
- **Apple Silicon macOS：**解压
  `CUKTECH-Screen-Controller-v0.4.1-macOS-arm64.zip`，双击
  **`Install CUKTECH Screen Controller.command`**。

两个安装器都会开启登录后自动运行的后台 Bridge。Windows 包自带完整运行环境；
macOS 安装器会在第一次运行时创建隔离 Python 环境。

### 当前要求

- Apple Silicon macOS 14+，或 Windows 10/11 x64；
- 电脑与 AP01 位于同一个未开启客户端隔离的局域网；
- 显示额度时，需要提前登录 Claude Desktop 与官方 Codex App；
- 实时额度与首次 OTA 云端操作需要互联网。
- **用户不需要购买小米网关**；共享 FDS 服务只在原厂屏首次安装时使用一次。

### 联网和设备准备（务必先看）

> [!IMPORTANT]
> **首次安装加载器前，必须先固定运行 Bridge 的电脑 IP。** AP01 固件保存的是
> `http://电脑IP:8765/screen.ap2b`（双页；旧单页为 `/screen.gif`）这个固定地址
> 不会跟随 DHCP 自动变化。优先在
> 路由器中设置 DHCP 静态分配；如果地址后来变化，先恢复原地址（不写 Flash）。只有
> 原地址无法恢复时，才固定新地址并重新生成、安装加载器（再写一次 Flash）。详细步骤：
> [Bridge 固定 IP 与地址变更恢复指南](docs/STABLE_IP_GUIDE.zh-CN.md)。

| 使用场景 | AP01 / 充电站 | 运行软件的电脑 | 是否需要互联网 |
| --- | --- | --- | --- |
| 已改造屏幕，显示本地图片 | 保持供电并连接家庭局域网 | 与 AP01 同一局域网，Bridge 运行 | 不需要；局域网正常即可 |
| 显示 Claude / Codex 额度 | 保持供电并连接家庭局域网 | 同一局域网，官方客户端已登录 | **电脑需要**，用于读取最新额度 |
| 完全原厂屏首次安装加载器 | 在米家完成配网并显示在线，安装期间稳定供电 | 能访问互联网和同一局域网 | **AP01 与电脑都需要** |

- 本项目日常通过 **Wi-Fi/LAN** 传图，不通过 USB 或底座触点传输显示内容；
- 不能使用访客网络，并应关闭路由器的 AP/客户端隔离；电脑使用网线也可以，
  只要和 AP01 处于能够互相访问的同一局域网；
- 如果 macOS 或 Windows 询问是否允许接收网络连接，请选择“允许”；VPN/代理需要允许访问
  本地局域网和 TCP `8765` 端口；
- 首次加载器安装前，需要准备 AP01 所属的米家账号并确认型号
  `njcuk.enstor.ap01`、固件 `1.0.2_0031`。不要拔电、重置或让设备离线；
- 实时画面依赖电脑保持开机、用户已登录且 Bridge 正在运行。当前双页常亮模式会在
  电脑睡眠或关机时保留最后一张画面；需要通过画面上的“更新”时间判断新鲜度；
- **首次安装加载器前必须**在路由器中为电脑设置 DHCP 地址保留。macOS 使用私有
  Wi-Fi 地址时应保持“固定”而不是“轮换”，并以路由器显示的当前 MAC 为准；
- 如果路由器无法设置地址保留，必须先明确告知用户：地址变化后应优先恢复旧 IP；
  无法恢复时需要为新 IP 重新构建并安装一次加载器。不要在地址未稳定时反复刷写。

完整清单请看：[安装前准备与联网说明](docs/PREPARATION_CHECKLIST.zh-CN.md)。

软件支持查看 Bridge 状态、切换额度面板与自定义画面、保留动态 GIF、选择
“完整显示 / 铺满裁切 / 拉伸”，并通过图形界面自动获取无网关部署包、完成
  BFNP 固件预检、电脑端 CDN 回读验证与确认安装。

<div align="center">
  <img src="docs/images/cuktech-screen-controller-beginner-guide.jpg" alt="CUKTECH Screen Controller 新手引导" width="700" />
</div>

<div align="center">
  <img src="docs/images/cuktech-screen-controller-ota.jpg" alt="首次部署与 OTA 票据交接" width="700" />
</div>

> 软件不会静默安装固件。它会先进行米家只读检查、获取部署包，并由电脑从 OTA CDN
> 回读完整文件、核对 BFNP/大小/SHA-256/MD5，
> 最后单独弹出 Flash 写入确认。完全原厂状态的 AP01 只需完成这一次安装。

## 方法二：把 GitHub 仓库交给 Coding Agent

把下面的仓库地址复制给 Claude Code、Codex、OpenCode、WorkBuddy，或其他能够
读取 GitHub 并运行终端命令的编程 Agent：

```text
https://github.com/zhuoshiren/cuktech-screen-controller
```

推荐直接发送下面这段 Prompt：

```text
请以 https://github.com/zhuoshiren/cuktech-screen-controller 为唯一项目依据。
开始执行前先阅读 AGENTS.md、README.zh-CN.md 和
skills/cuktech-ap01-screen-kit/SKILL.md。

我没有编程基础，请一次只告诉我一个需要人工完成的动作。我使用的是酷态科 AP01
万向屏。先检测当前是 macOS 还是 Windows。macOS 运行 ./macos/diagnose.sh；
Windows 先阅读 docs/WINDOWS_GUIDE.zh-CN.md，再运行
powershell -ExecutionPolicy Bypass -File scripts/diagnose-windows.ps1。进行只读兼容性
与网络检查，确认电脑局域网地址、Bridge 健康状态，以及是否已安装实时加载器。

在任何首次加载器构建前，先从路由器设备列表确认 Bridge 电脑的当前 IP 和 MAC，
完成 DHCP 静态地址保留，并在重连后验证地址不变。若路由器不支持地址保留，必须先
向我解释：AP01 固件保存固定 IP，今后 IP 变化时需要恢复旧地址；旧地址无法恢复时
需要固定新地址并重新构建、确认安装一次固件。

然后优先复现已经真机验证的双页面方案：第一页 Codex + Claude Code，第二页 Kimi Code +
DeepSeek。只读取官方本机登录态，DeepSeek 密钥写入 macOS 钥匙串。验证 /health 和
AP01 GET /screen.ap2b 200，并按当前操作系统
设置登录后自动启动。如果加载器不存在，先构建和校验完全匹配的镜像，真正安装前
向我确认。日常刷新必须使用 /tmp 的 RAM 槽位，不要重复刷固件。
```

不支持 Codex Skill 格式的软件，也可以直接读取 `SKILL.md` 作为完整操作手册。
仓库还提供 `AGENTS.md`、`CLAUDE.md` 和跨平台配置脚本。Agent 克隆后按系统运行：

```bash
./macos/diagnose.sh       # 只读检查，不修改设备
./scripts/setup-macos.sh  # 安装 Bridge 并设置登录自启

# Windows PowerShell
.\scripts\diagnose-windows.ps1
.\scripts\setup-windows.ps1 -InputImage "C:\Pictures\screen.png"
```

## 首次安装与日常刷新不是一回事

```mermaid
flowchart LR
  A["原厂 AP01"] -->|"仅首次：安装实时加载器"| B["写入一次 Flash"]
  B --> C["已经具备实时显示能力"]
  C -->|"日常：获取 screen.ap2b"| D["写入 /tmp RAM 槽位"]
  D --> E["更新画面，不重复刷固件"]
```

- **首次加载器安装**：仅适配型号 `njcuk.enstor.ap01`、固件 `1.0.2_0031`，
  会发生一次固件 Flash 写入。
- **日常图片与额度刷新**：双页 GIF 只轮换写入 `/tmp/.ap01p{0,1,2}{m,o}.gif`，不写固件分区
  或资源分区，不会因为五分钟刷新一次而把 Flash 刷坏。
- 运行 Bridge 的电脑暂时离线时，当前双页常亮模式会保留最后成功画面；Bridge
  恢复后继续刷新。请用页面顶部更新时间判断数据是否仍然新鲜。

### 如何判断屏幕上的额度是不是最新的

- Bridge 每 5 分钟重新读取四个服务的官方本机登录态或官方 API；
- 在线卡片的计划徽章带绿色状态点和最后成功刷新时间，可与屏幕顶部时钟直接比较；
- 某个服务暂时采集失败时，常亮模式保留该服务最后一次成功数据，并把错误写入本机
  `/health` 与清洗后的 JSON；
- 电脑关机时 AP01 无法获得新画面，因此屏幕上的更新时间不会前进。常亮是本方案的
  明确需求，不应把旧更新时间误认成刚刷新；
- 连接恢复并成功刷新后，下一次 AP01 轮询会自动恢复最新额度面板。

## 这是什么？

这是为酷态科 10 号充电站可拆卸显示屏 AP01（`njcuk.enstor.ap01`）准备的一套 macOS/Windows 图形软件、开源工具与 Codex Skill，可用于：

- 将任意图片转换为 AP01 可流畅显示的 GIF89a；
- 设计高可读性的 320×240 信息屏；
- 从 Codex、Claude Code、Kimi Code 与 DeepSeek 的官方来源获取额度；
- 通过 macOS 或 Windows 电脑的局域网 Wi‑Fi 自动刷新显示内容；
- 为 AP01 `1.0.2_0031` 安装一次性实时加载器；
- 此后不再刷固件，只替换本地 GIF 即可换内容。

额度面板只是一个示例。你可以替换为艺术图、日历、天气、充电功率、构建状态、Home Assistant 指标或任何你喜欢的信息。

## 核心能力

| 自定义内容 | 双页 Coding 面板 | 轻量运行时 |
| --- | --- | --- |
| 将图片转换为经过校验的 320×240 GIF89a。 | Codex/Claude Code 严格额度；Kimi 周/5 小时；DeepSeek 余额。 | 帧数受控的动画，通常低于 90 KB。 |
| 支持 `contain`、`cover`、`stretch`。 | Codex/Claude 与 Kimi/DeepSeek 各占一个旋钮页面。 | AP01 在 `/tmp` RAM 中轮换文件，不写资源分区。 |

## 工作架构

```mermaid
flowchart LR
  A["自定义画面或数据"] --> B["macOS / Windows 渲染器与 Bridge"]
  B -->|"GIF89a · 320×240 · HTTP"| C["AP01 实时加载器"]
  C --> D["/tmp/.ap01p{0,1,2}{m,o}.gif\n三代双页 RAM 槽位"]
  D --> E["LVGL 虚拟形象页面"]
```

首次固件安装只负责加入加载器。此后的画面更新均通过 Wi‑Fi 下载并写入 RAM。

## 高级与手动配置

### 1. 建立环境

```bash
git clone https://github.com/zhuoshiren/cuktech-screen-controller.git
cd cuktech-screen-controller
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Windows PowerShell 使用：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 把任意图片变成 AP01 屏幕

```bash
.venv/bin/python ap01_prepare_screen.py ./my-artwork.png artifacts/screen.gif \
  --fit contain --background '#01040B'
.venv/bin/python ap01_screen_bridge.py artifacts/screen.gif --port 8765
```

转换器会输出 320×240 GIF89a：静态图会生成稳定的双帧容器，动态 GIF 会在限制
帧数与体积的同时保留可见动画。之后只需要原子替换 `artifacts/screen.gif`，
AP01 会在下一次刷新时获取新内容。

### 3. 运行四服务双页面额度面板（macOS）

先登录 Codex、Claude Code 与 Kimi Code。DeepSeek API Key 不写入文件，使用安全输入框
直接保存到 macOS 登录钥匙串：

```bash
swift macos/store-deepseek-key.swift
```

Claude Code 额度来自官方 `statusLine` 输入。把下面这一行作为**副作用**加入现有
status-line 脚本（先完整读取 stdin，再继续使用同一份 `$input` 绘制原状态栏）：

```bash
printf '%s' "$input" | /ABSOLUTE/REPO/.venv/bin/python \
  /ABSOLUTE/REPO/claude_statusline_cache.py 2>/dev/null || true
```

然后把已确认的 AP01 私有 IPv4 写入本地 allow-list，启动双页 Bridge：

```bash
printf '%s\n' 'AP01_PRIVATE_IP' > artifacts/ap01-ip
printf '%s\n' 'coding' > artifacts/ap01-mode
./macos/ap01-bridge-runner.sh
```

在 `artifacts/coding-balances-codex-claude@2x.png` 与
`artifacts/coding-balances-kimi-deepseek@2x.png` 查看预览。Bridge 提供：

```text
http://COMPUTER_LAN_IP:8765/screen.gif
http://COMPUTER_LAN_IP:8765/screen.ap2b
http://127.0.0.1:8765/api/v1/balances
http://COMPUTER_LAN_IP:8765/health
```

`/api/v1/balances` 仅允许本机访问；LAN 端只允许 allow-list 中的 AP01 和本机地址。
完整的 Claude `statusLine` 接入、Keychain 和 provider 验证步骤见
[双页面真机案例](skills/cuktech-ap01-screen-kit/references/two-page-coding-dashboard.md)。

## 首次配置实时固件

内置二进制 Patch 仅适配 AP01 型号 `njcuk.enstor.ap01`、固件
**`1.0.2_0031`**。构建前让运行 Bridge 的电脑与 AP01 连接到同一个未隔离
局域网，并在路由器中固定这台电脑的 DHCP 地址。

不要把“固定地址”当成可选优化。加载器写入的是字面量 IPv4 URL；构建前请先按照
[固定 IP 指南](docs/STABLE_IP_GUIDE.zh-CN.md)完成路由器 DHCP 保留并重连验证。

```bash
# 通过已登录的米家账户确认并下载对应原厂固件。
.venv/bin/python mi_cloud.py firmware
.venv/bin/python mi_cloud.py download

# 构建带兜底画面的兼容镜像，并注入本地 HTTP 加载器。
.venv/bin/python ap01_custom_ota.py artifacts/screen.gif \
  --firmware artifacts/ap01-1.0.2_0031.bin \
  --output artifacts/ap01-1.0.2_0031-screen-compat.bin

.venv/bin/python ap01_realtime_patch.py \
  --input artifacts/ap01-1.0.2_0031-screen-compat.bin \
  --output artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --build-dir artifacts/realtime-build \
  --url http://COMPUTER_LAN_IP:8765/screen.ap2b \
  --refresh-seconds 300

# 上传后先由电脑回读 CDN，逐字节验证；这一步不会连接 AP01。
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --upload-only --url-output /tmp/ap01-ota-url.txt
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --verify-download --ota-url-file /tmp/ap01-ota-url.txt

# 只有设备所有者明确确认后才安装同一份镜像。
.venv/bin/python ap01_install_firmware.py \
  artifacts/ap01-1.0.2_0031-screen-realtime.bin \
  --install --ota-url-file /tmp/ap01-ota-url.txt
```

最终安装前先启动 Bridge。日志中出现
`AP01_IP "GET /screen.ap2b" 200`，即表示双页面端到端实时刷新已打通。

### 小米 FDS 上传前提

#### 普通用户：不需要拥有网关

CUKTECH Screen Controller 0.4 起提供受限的共享 FDS 票据服务。软件只会发送
电脑的私有局域网 Bridge 地址、刷新间隔、目标型号和固件版本；用户的米家账号、
密码、Token、AP01 DID、Claude/Codex 登录态都不会发送给共享服务。服务端不接受
任意 BIN，只能从 SHA-256 固定的 `1.0.2_0031` 原厂镜像构建经过审查的实时加载器。

图形软件操作顺序：

1. 点击“无网关：一键获取部署包”；
2. 软件确认 AP01 为 `njcuk.enstor.ap01 / 1.0.2_0031` 且米家在线；
3. 下载并核对 BFNP、大小、SHA-256 与 MD5；
4. 点击“电脑端 CDN 回读验证”；这一步不连接 AP01；
5. 验证成功后点击“确认后安装”，并在最终弹窗中明确确认。

共享服务仅解决一次性的 FDS 上传，最终 `miIO.ota` 仍由用户本机登录的米家账号
发给用户自己的 AP01。安装成功后，日常画面全部走局域网 `/tmp` RAM，不依赖
共享服务或任何网关。服务协议和自建说明见
[共享 FDS 服务运维文档](docs/FDS_RELAY_OPERATOR.zh-CN.md)。

#### 高级用户：自己的网关或手动票据

AP01 自身没有小米云端的 FDS 上传配置。把 AP01 的 DID/model 传给
`/home/genpresignedurl`，会稳定返回 `code=-6`、`invalid config for fds`。
仓库原本的传输链路实际使用了两个不同的设备身份：

- 账号中的 `lumi.gateway.*` 或 `xiaomi.gateway.*` 网关只负责申请 FDS
  上传地址；
- AP01 的 DID 只在后续 `miIO.ota` 下载指令中作为目标设备。

因此不存在可以手工填写的 AP01 bucket、隐藏 model 或特殊 DID。如果 AP01
账号没有具备 FDS 配置的网关，可由可信的网关账号上传**完全相同的 BIN**，
再把短时有效的签名 URL 交给设备所有者的电脑执行回读验证。

在含网关的上传账号/Mac 上执行：

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/screen-realtime.bin \
  --upload-only --url-output /tmp/ap01-ota-url.txt
```

如果自动识别不明确，可以补充该账号真实拥有且具备 FDS 配置的网关：
`--fds-did DID --fds-model lumi.gateway.MODEL`。随便填写 model 或使用 AP01
的 DID 都不能绕过服务端配置。

随后把 `/tmp/ap01-ota-url.txt` 发给 AP01 所属账号，在 URL 失效前执行：

```bash
.venv/bin/python ap01_install_firmware.py \
  artifacts/screen-realtime.bin \
  --verify-download --ota-url-file /path/to/ap01-ota-url.txt --timeout 360
```

这条命令由电脑从官方 OTA CDN 下载完整对象，核对 BFNP、大小、SHA-256 和 MD5，
不会创建米家会话，也不会向 AP01 下发 OTA。上传端和验证端必须使用逐字节相同的
`screen-realtime.bin`，中间不要重新构建。AP01 1.0.2_0031 上的旧
`--download-only` 可能继续自动安装，因此已在公开工具中禁用。

给自动化 Agent 使用的完整故障分流与验收清单见：
[AP01 无外置网关时的 FDS 解决方案](docs/AP01_FDS_NO_GATEWAY_SOLUTION.zh-CN.md)。

## 屏幕协议

| 要求 | 参数 |
| --- | --- |
| 物理分辨率 | 320×240 |
| 容器 | GIF89a |
| 动画 | 至少 2 帧；推荐慢速动画 |
| 推荐体积 | ≤ 90 KB |
| 固件槽位上限 | 221,445 bytes |
| 运行时加载器上限 | 256 KiB |
| 系统时间预留 | 保留第 0–39 行以显示原厂时钟/日期 |

## Flash 写入行为

固件安装会写入一次 Flash；普通内容与额度刷新不是这样。实时加载器只会写入以下 RAM 路径：

```text
/tmp/.ap01p{0,1,2}{m,o}.gif
/tmp/.ap01q.meta
/tmp/.ap01q.ack
/tmp/.ap01q.ui
/tmp/.ap01blank.gif
```

因此，修改画面或刷新额度时，**不会反复写入** AP01 固件与资源分区。

## 隐私

- Codex、Claude Code 与 Kimi Code 使用本机已经登录的官方客户端状态；DeepSeek
  使用官方余额 API。
- Claude 缓存只保留 `rate_limits` 中的百分比、重置时间和套餐，不保留会话 ID、
  对话路径、正文或 Token；DeepSeek Key 只保存在 macOS 钥匙串。
- 额度文件权限统一为 0600；JSON 只包含经过清洗的数据且仅允许本机访问。画面端点
  只接受本机与精确匹配的 RFC1918 AP01 白名单，持久日志不记录二者地址。
- 仓库不会上传固件、米家账号凭据、签名下载链接、设备 ID、局域网 IP 或运行产物。

## Coding Agent 与 Skill

仓库内包含可独立安装的 Codex Skill：

```bash
cp -R skills/cuktech-ap01-screen-kit ~/.codex/skills/
```

安装后可直接使用：

```text
Use $cuktech-ap01-screen-kit to turn this image into an AP01 screen.
Use $cuktech-ap01-screen-kit to safely deploy the verified two-page Codex, Claude Code, Kimi Code and DeepSeek dashboard.
Use $cuktech-ap01-screen-kit to diagnose why AP01 is not refreshing.
```

Skill 内含可复用项目模板、图片转换器、额度面板、固件工作流与网络诊断说明。

## 目录结构

```text
ap01_prepare_screen.py     任意图片转 AP01 安全 GIF
ap01_screen_bridge.py      在局域网提供可替换画面
quota_dashboard.py         旧版一页面板与兼容采集器
ap01_wifi_bridge.py        自动刷新并提供额度面板
coding_balances_bridge.py  渲染并提供四服务 AP2B 双页面
claude_statusline_cache.py 安全缓存 Claude Code 官方额度字段
ap01_realtime_patch.py     构建 1.0.2_0031 RAM 加载器
ap01_install_firmware.py   通过小米 OTA 下发已构建镜像
realtime_payload/          AP01 加载器源码
skills/                    可安装的 Codex Skill
macos/                     SwiftUI 软件、安装器与 Release 打包脚本
windows/                   Windows 图形软件、运行时、安装器与打包脚本
scripts/*windows.ps1       Windows 源码环境配置与只读诊断
```

## 开发

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python scripts/render-two-page-demo.py
```

贡献规范见 [CONTRIBUTING.md](CONTRIBUTING.md)；分享日志或报告漏洞前请先阅读
[SECURITY.md](SECURITY.md)。项目采用 [MIT License](LICENSE)；上游作者和本 Fork
的修改范围记录在 [NOTICE.md](NOTICE.md)。
本项目与酷态科、小米、OpenAI、Anthropic、Moonshot AI、DeepSeek 均无隶属或背书关系；
各商标归其权利人所有。
