"""Prompts 模块 — 集中管理 LLM prompt 模板

职责分工：
- 本子包：代码内静态常量 prompt（业务逻辑强绑定，无运行时调优需求）
- app.services.prompt_service：数据库存储的可动态调优 prompt（带 version / is_active）

新 wave 接入 prompt 时，请先判断属于哪一类：
- 静态、不需要 A/B 测试 → 放入本子包
- 动态、需要热更新 → 放入 prompt_service
"""
