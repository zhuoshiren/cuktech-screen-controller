# Contributing / 参与贡献

## English

1. Keep each AP01 page 320×240 GIF89a with two or more frames; preserve the
   AP2B header and single-active-decoder invariant for two-page changes.
2. Keep generated firmware, account data, local IPs, device IDs, and artifacts
   out of commits.
3. Add or update a focused test for renderer, converter, or patcher changes.
4. Run `python -m unittest discover -v` before opening a PR.
5. For a firmware offset change, include the firmware version, exact validation
   evidence, hook readback, recovery CRC, and an AP01 request trace.

## 简体中文

1. 保持每页 320×240、GIF89a、至少两帧；双页修改还要保持 AP2B 头部与
   单活动解码器约束。
2. 不提交生成固件、账号数据、局域网 IP、设备 ID 与运行产物。
3. 修改渲染器、转换器或 Patch 时，补充对应的聚焦测试。
4. 提交 PR 前运行 `python -m unittest discover -v`。
5. 修改固件偏移时，附上固件版本、验证证据、Hook 回读、Recovery CRC 与
   AP01 请求日志。
