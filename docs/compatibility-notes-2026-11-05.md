# 图片兼容性记录（2026-11-05）

## 当前结论

- 本地目标仓库是 `E:\chatgpt2api`，不是 `chatgpt2api-personal`。
- 上游 PR 408 已在本地 `pr-406` 分支合并，提交为 `0b7b2d3`，内容是全屏图片编辑器、mask 局部编辑和前端图片编辑工作台。
- HAR `C:\Users\macky\Downloads\chatgpt.com.har` 共 31 条请求；图片对话使用 `model=auto`，下载资源的响应类型为 `image/gif`，文件约 439486 bytes。HAR 没有保存完整 SSE 正文，因此不能仅凭该文件确认上游实际模型名，也没有证据证明请求体里出现了 `gpt-image-2.6`。

## 代码兼容策略

- `gpt-image-2.6`、`codex-gpt-image-2.6` 以及 `plus/team/pro` 前缀已加入图片模型识别和 `/v1/models` 动态列表。
- 官网链路的 `gpt-image-2.6` 优先使用 `default_upstream_model_name_26`，未配置时保持 HAR 已确认的上游 `model=auto`；不会继承旧的 2.5/默认模型名。
- Codex 链路的 `codex-gpt-image-2.6` 工具名默认为 `gpt-image-2.6`，可通过配置读取。
- 图片下载保留上游 `Content-Type`，存储层同时按真实图片格式识别扩展名和 MIME；GIF 会保存为 `.gif`，索引记录 `mime_type=image/gif`，WebDAV 上传和远程图片响应也会使用正确 MIME。
- 缩略图仍统一生成 PNG，原始 GIF 不被重编码，下载 ZIP 保留原始扩展名。

## Sentinel 求解器

- 远端 154 已运行私有 `chatgpt2api-sentinel-solver`（Chromium，容器内 8080 端口）。主服务通过 `CHATGPT2API_SENTINEL_SOLVER_URL` / `CHATGPT2API_SENTINEL_SOLVER_KEY` 调用 `/v1/turnstile`；客户端只发送 `dx`、`p` 和 prepare challenge 数据。
- 本地代码已加入同样的 solver 客户端；配置了 solver 时优先使用 Chromium，未配置时保留旧本地求解器作为兼容回退。prepare/finalize 的 `p`、PoW、Turnstile 和 solver UA 会保持一致，finalize 始终提交三个字段。
- 本地真实请求使用 154 取出的两条记录时返回了 403 `Unusual activity`；两条记录的元数据为 `source_type=codex`，但用户确认其实际可能用于 Web 链路，因此不能把该字段本身当作失败原因。这不是 GIF 存储代码的失败证据；仍需要一条能完成 Web 会话的有效记录来验收 GIF。

## Web / Codex 账号边界（2026-11-05 追加）

- 用户确认 154 上的部分记录实际用于 Web 链路，只是 `source_type=codex` 元数据可能填错；因此网页模型不能简单硬过滤 `source_type=web`，当前实现保持网页模型不指定 `source_type`，只有 `codex-*` 模型才要求 `source_type=codex`。
- 对 154 当前首两条记录做了只读核对：JWT client id 为 `app_2SKx...`，没有 `chatgpt_account_id`；`/backend-api/accounts/check` 返回 guest/null，网页 conversation 仍返回 403 `Unusual activity`。这证明当前记录尚未完成可用 Web 会话验收，但不能单凭字段断言账号归属；不要把它们当作 GIF 成功证据。
- 已移除本轮临时远端账号副本和本地探测脚本；没有修改 154 数据库或账号类型。

## 验证记录

```text
python -m pytest -q test/test_image_download_parts.py test/test_image_model_25.py test/test_image_storage_service.py test/test_image_service_gif.py test/test_v1_models.py test/test_web_conversation_request.py test/test_sentinel_solver_client.py -k "not http"
29 passed, 1 deselected
python -m compileall -q services utils api main.py
exit=0
```

本地服务启动成功，`/v1/models` 返回 HTTP 200；但本地 `data/accounts.json` 为空，所以没有执行本地真实图片请求。全量非 HTTP 测试仍包含仓库内既有的 Outlook fixture、图片任务 API 鉴权和多图轮询失败，不能把它们混入本次 Web/GIF 兼容性结论。真实 GIF 生成仍需使用已配置账号通过本地服务接口验收，并用 Pillow 检查文件头、帧数和尺寸。
