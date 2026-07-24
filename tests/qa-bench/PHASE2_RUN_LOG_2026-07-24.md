# qa-bench D6 Phase 2 真跑日志（2026-07-24）

> 状态：**待主指挥 SSH 真跑后回填**
>
> 本占位文件不包含真实结果；Agent C-2 未执行 1000 题调用。

## 1. 执行信息

| 字段 | 主指挥回填 |
|---|---|
| 执行人 |  |
| 执行主机（脱敏） |  |
| Git commit |  |
| 开始时间 |  |
| 结束时间 |  |
| 总耗时 |  |
| Backend / model |  |
| 数据库 | `microbubble_test` / 待确认 |
| 首次运行退出码 |  |
| 是否重跑 |  |
| 重跑退出码 |  |

## 2. 真跑结果

| 指标 | 主指挥回填 |
|---|---|
| 题目数 |  |
| Rounds |  |
| 理论调用数 | 3000 |
| 实际调用数 |  |
| PASS |  |
| FAIL |  |
| ERROR |  |
| EMPTY / UNKNOWN |  |
| 全局 pass rate |  |
| Gate threshold | 90% |
| Gate verdict |  |

## 3. 7 维评分

| 维度 | 平均分 | 备注 |
|---|---:|---|
| intent |  |  |
| tool |  |  |
| content |  |  |
| rich |  |  |
| defense |  |  |
| perf |  |  |
| consistency |  |  |

## 4. Per-intent 六类别

| Intent | 题数 | Pass rate | 主要失败原因 |
|---|---:|---:|---|
| meeting |  |  |  |
| task |  |  |  |
| knowledge |  |  |  |
| member |  |  |  |
| project |  |  |  |
| drive |  |  |  |

## 5. 产物

| 产物 | 路径 / 校验值 |
|---|---|
| 原始 JSON |  |
| Markdown 报告 |  |
| 终端日志（脱敏） |  |
| 失败或重跑产物 |  |

## 6. 异常与重跑记录

- 首次运行异常：
- 根因分类：
- 修复动作：
- 是否执行唯一一次重跑：
- 重跑结果：

## 7. 最终结论

- [ ] Phase 2 真跑完成且 Gate PASS
- [ ] Phase 2 真跑完成但 Gate FAIL，已建立 Phase 3 修复项
- [ ] Phase 2 数据不完整，不形成新 baseline
- [ ] Phase 2 两次运行失败，保留旧报告

失败回滚固定标注（需要时取消引用并保留原文）：

> **Phase 2 失败, Phase 1 dry-run 100 题仍 PASS**

主指挥结论：


## 8. 签字确认

- 主指挥：
- 回填日期：
- Secret 泄漏检查：`PASS / FAIL`
- 1000 题 × 3 rounds 检查：`PASS / FAIL`
- 90% gate 复算检查：`PASS / FAIL`
