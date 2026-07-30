# tests/dev_port_x25/

W89-X-25 类 20.80 守恒验证: visual + e2e spec 必无硬编码 dev port, 必用
`process.env.BASE_URL`, 兜底 URL 与 vite dev (`package.json` `--port 3000`)
对齐。

详见 `test_base_url.py` 4 个 case。

跑法:

```bash
SKIP_DB_SETUP=1 pytest tests/dev_port_x25/ -v
```
