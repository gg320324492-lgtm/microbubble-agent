# W87-X-4a typing imports timeout flake 修复（2026-07-30）

## 背景与 root cause

W87-X-3 集成 e2e 据实上报 `test_typing_imports_exit_zero` 偶发超时。实际测试位于 `tests/precommit/test_hooks_executable.py`；派工 brief 所指 `tests/precommit/test_config_valid.py` 仅校验 YAML 配置，不包含该测试或 subprocess timeout。

`tests/precommit/test_hooks_executable.py` 原先给 `scripts/check_typing_imports.sh` 设置 `timeout=60`。脚本会遍历 `app/agent`、`app/services`、`app/api` 下的 Python 文件，并对每种 typing 名称执行 grep；集成运行约 63 秒，复跑可达 73 秒，因此 60 秒阈值紧贴或低于实际耗时，形成边界 flake。脚本本身属于 CLAUDE.md 永久纪律，本次未修改。

## 最小修复

仅将 `test_typing_imports_exit_zero` 的 subprocess timeout 从 60 秒提高到 180 秒，并保留注释说明该余量满足实测耗时至少 2 倍的要求。

## 验证

完整 precommit 套件：

- `SKIP_DB_SETUP=1 pytest tests/precommit/ -v -m precommit`
- 结果：14 passed、4 skipped、0 failed，70.48 秒。

目标测试连续复跑 3 次：

- 第 1 次：PASS，69.21 秒
- 第 2 次：PASS，61.51 秒
- 第 3 次：PASS，73.38 秒

三次均稳定通过，180 秒 timeout 对当前耗时留有充足余量。

## 派工 v6 §5 反馈：类 20.33

**pytest timeout 必须不低于被测脚本实测时间的 2 倍。**

本案脚本已知约 63 秒，连续复跑最高 73.38 秒；原 60 秒 timeout 低于真实上界而产生 flake。修复取 180 秒，既超过 `73.38 × 2 ≈ 146.76` 秒，也为 Windows/Git Bash、磁盘和 CI 负载波动保留余量。
