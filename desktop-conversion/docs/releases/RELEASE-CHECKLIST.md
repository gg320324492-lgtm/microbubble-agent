# 发布列车审计清单（v1.1.0 起固化，来源：R-9 复盘）

每次发布列车（tag 类工单）交付前，执行端与总指挥按序核对：

## 顺序铁律

1. **CHANGELOG 先于 tag**：版本段落提交完毕后再打 tag（R-9 曾 tag 后补 CHANGELOG，靠 Release notes 兜底——不再允许）
2. test tag 首航（`vX.Y.Z-ci.N`）→ CI 全绿**含 OSS 镜像成功** → 删除 test tag 与其 Release（远端零残留）→ 才推正式 tag
3. 正式 tag 不可变（v1.0 起）；tag 后只允许文档类提交进 HEAD，Release notes 承载差异

## 前置门（推 tag 之前逐项确认）

- [ ] GitHub Secrets `OSS_UPLOAD_AK/SK` 有效（欠费/禁用会让 CI 在 OSS 镜像步红——自检已前置到上传前）
- [ ] 版本两处同步：`package.json` version 与 `src/shared/constants.ts` APP_VERSION
- [ ] 基线测试数与 typecheck 0 错；无新增依赖（electron-updater 唯一例外）
- [ ] 保护路径零改动（`git status --short` 自证）；他轨提交不回退不重排，报告注明

## 发布后四连测（总指挥独立执行）

- [ ] 双源 sha256 逐字一致（OSS 域名下载 vs GitHub Release digest）
- [ ] `https://releases.mnb-lab.cn/releases/latest.yml` 匿名 200 且 version 正确
- [ ] 安装包直链 200
- [ ] Release 形态：prerelease=false、notes 完整、三件套齐

## 关联

- 落地页 `scripts/download-page.html` 的版本号/哈希/体积须与本次发布一致（自动化根治见 P2「落地页版本号自动化」）
- 更新源域名：`releases.mnb-lab.cn`（feed-config 纯函数 14 用例守护）
