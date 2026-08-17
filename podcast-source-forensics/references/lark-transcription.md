# 飞书妙记转写通用链路

## 数据边界

此流程会把本地音视频上传到当前用户自己的飞书云空间，并由飞书生成妙记。不要用于公司或个人不允许上传到飞书的敏感材料。若用户尚未明确授权上传，执行前说明这一点并取得确认。

Skill 不保存或分发任何 API、密钥、令牌、设备码、个人账号、个人目录或既有妙记 ID。所有命令依赖执行者自己的 `lark-cli` 配置。

## 前置检查

1. 确认 `lark-cli` 可用。
2. 首次使用时运行 `lark-cli config init --new`，按 CLI 提示完成当前用户的应用配置和用户授权。
3. 用 `lark-cli auth status --json --verify` 检查登录态；不要把返回的身份信息或令牌写入 Skill、报告或分享包。
4. 所有文件参数使用当前工作目录下的相对路径。飞书 CLI 会拒绝不安全的绝对路径。

不要要求使用者手工抄出或发送 `appSecret`、访问令牌。遇到缺少权限时，以 CLI 返回的 `missing_scopes` 和修复提示为准，只申请完成当前任务所需的最小权限。

## 标准命令

在含音频文件的工作目录中执行：

```powershell
# 1. 上传音频到当前用户的飞书云空间，读取成功结果中的 file_token
lark-cli drive +upload --file ./audio/episode.m4a --as user

# 2. 用 file_token 创建妙记，读取 minute_url 或 minute_token
lark-cli minutes +upload --file-token <file_token> --as user

# 3. 等待妙记就绪，并导出完整逐字稿
lark-cli minutes +detail --minute-tokens <minute_token> `
  --wait-ready --transcript --overwrite `
  --output-dir ./transcript --as user
```

身份是整个链路的状态。`file_token` 和 `minute_token` 由 `--as user` 取得，后续命令继续显式使用 `--as user`，不要依赖默认身份，也不要在权限错误时切换成 bot。

`minutes +detail` 必须显式传 `--transcript`；不传时只会返回基础信息。上传后立即读取必须传 `--wait-ready`。

## 成功判断

- 以进程退出码 0 或 JSON 信封的 `ok == true` 判断成功。
- 不要用顶层 `code == 0` 判断；成功信封通常没有该字段。
- 逐字稿默认是带说话人和相对时间戳的 Transcript。确认文件从开头延续到接近节目总时长。
- 对节目做独立分析时以 Transcript 为主，不照搬妙记 AI Summary。

## 常见错误

| 症状 | 处理 |
|---|---|
| `unsafe file path` | 切换到工作目录，改用 `./audio/...`、`./transcript` 等相对路径 |
| `missing_scope` | 保持 `--as user`，按错误提示完成最小权限授权后重试 |
| 对某条资源无权访问 | 请求资源所有者给当前用户授权，不切换身份绕过 |
| 返回了元信息，没有逐字稿 | 补上 `--transcript` |
| 妙记仍在处理中 | 使用 `--wait-ready` 并等待，不把空产物当成功 |
| 英文人名或引文识别错误 | 保留原始副本，在分析副本中做有依据的最小校正 |

## 隐私清理

分享 Skill 或报告前，不包含：

- 任意 API key、secret、access token、refresh token 或 device code。
- 真实 `file_token`、`minute_token`、文档 token 或授权链接。
- 当前用户名、个人飞书 open_id、个人工作目录和账号配置。
- 完整第三方播客逐字稿。只保留研究所需的短引文和时间戳。
