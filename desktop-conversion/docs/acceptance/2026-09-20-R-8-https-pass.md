# R-8 附加项验收：releases.mnb-lab.cn HTTPS 证书事务（2026-09-20）

## 结论

**通过**。`https://releases.mnb-lab.cn` 证书托管生效，feed 与安装包经自定义域名匿名 HTTPS 可达，R-8 国内分发连同 HTTPS 彻底收官。

## 背景与路线

- 用户拍板：Let's Encrypt 扩 SAN 路线，为 `releases.mnb-lab.cn` 单域签发（存量 `mnb-lab.cn`/`agent.mnb-lab.cn`/`mnb-lims.cn` 由 ECS certbot HTTP-01 管理，互不干扰）
- 工具：ECS 新装 acme.sh v3.1.5（`dns_ali` 插件 DNS-01，与 certbot 并存），CA = Let's Encrypt

## 执行时间线（2026-09-20 凌晨，CST）

1. 03:40 / 03:44 / 03:51 三次签发均失败：`Error adding TXT record`
2. `--debug 2` 取证：阿里云 DNS API 返回 `Forbidden.RAM` / `ImplicitDeny`，缺失动作 `alidns:DescribeDomainRecords`，属主 UID 与 workbench-backup 用户 ID 一致 → **根因：该 RAM 用户只授过 OSS 权限，DNS 权限从未落上**
3. RAM 控制台补授 `AliyunDNSFullAccess`（1/1 成功）
4. 03:58 签发成功（第 1 张）；因证书私钥两次随终端输出进入对话，以 `--force --always-force-new-domain-key` 换钥两次（04:03、约 04:07）——**线上服务之钥（第 3 把）从未进入对话**
5. 证书经「数字证书管理服务（CAS）→ 上传证书」进 OSS 证书托管（新版 OSS 面板公钥/私钥框为只读展示，自传证书必须走 CAS 路径；证书文件=叶子块、证书链=中间 3 块、私钥=EC 块）
6. 约 04:20 OSS 域名管理选中证书生效

## 终验证据（2026-09-20 04:22-04:24 CST，总指挥侧独立执行）

| 项 | 结果 |
| --- | --- |
| TLS 证书 | `subject=CN=releases.mnb-lab.cn`，`issuer=Let's Encrypt YE2`，`notAfter=Dec 18 19:08:39 2026 GMT`，链校验通过 |
| 证书指纹（sha256） | `F9:46:C0:02:28:A9:30:BB:36:96:78:BF:73:C0:BE:A3:ED:9F:43:00:32:BE:36:13:44:18:C0:AC:E8:A1:18:40`（留档，后续可与 ECS 文件比对） |
| feed | `GET https://releases.mnb-lab.cn/releases/latest.yml` → 匿名 200，`version: 1.0.1` 完整返回 |
| 安装包 | `GET https://releases.mnb-lab.cn/releases/MicroBubbleWorkbench-1.0.1-setup.exe` → 200，`Content-Length: 92193596`，与 feed 清单 size 一致 |

注：notBefore 较签发时刻回拨约 1 小时为 Let's Encrypt 惯例（防时钟漂移），线上证书与第 3 次签发时间吻合。

## 安全事务与遗留

- **OSS AK 轮换（待办，必办）**：workbench-backup 用户的 AK Secret 曾两次进入对话记录 → HTTPS 收官后执行轮换仪式：RAM 控制台为该用户禁用旧 AccessKey、新建一对，更新 GitHub Secrets（OSS_UPLOAD_AK/SK）与应用设置页 OSS 配置。全程 Secret 不进对话
- **feed 域名切换（随下一发布列车）**：`UPDATE_FEED_HOST` 从 OSS endpoint 切 `https://releases.mnb-lab.cn`（`apps/desktop/src/shared/constants.ts:16` 注释预留的一行，R-8 设计内变更）；现网 v1.0.1 客户端继续走 OSS endpoint（HTTPS 本就可用），无紧迫性
- acme.sh 凭证已存 ECS `~/.acme.sh/account.conf`，ARI 自动续期已排（下次 2026-11-19），续期 TXT 写入权限已具备，无需人工干预
