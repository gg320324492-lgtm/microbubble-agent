# 2026-10-29 agent.mnb-lab.cn 全站 ERR_CERT_DATE_INVALID —— 证书续期静默失败 30 天

> 事故档案（只增不改）。触发链路：**一个还在有效期内的证书**、**一个每天跑 4 次的
> certbot.timer**、**一条没人看的错误日志** —— 三者同时成立，而 HTTPS 对所有客户端
> 实际不可用长达 23 小时没人发现；根因的第一层早在 **30 天前**就开始了。

## 现象

- 2026-10-29 用户报：`https://agent.mnb-lab.cn/drive` → `NET::ERR_CERT_DATE_INVALID`。
- 本机复现：`curl https://agent.mnb-lab.cn/health` → `SEC_E_CERT_EXPIRED (0x80090328)`。
- 容器内 `openssl s_client` 看到：agent 证书 `notAfter=Oct 28 12:03:47 2026 GMT`（已过期）。
- **两端时钟一致**（本机与云端都是 Oct 29 ~11:23 UTC）⇒ **不是本机时间问题**，
  是证书真的过期了。

## 根因链（三层，逐层修好才看得见下一层）

### 第一层：certbot 续期从 2026-09-28 起就一直在失败

`agent.mnb-lab.cn` 那条 certbot lineage 用 `authenticator = standalone` ——
该插件要**独占 80 端口**才能完成 HTTP-01 挑战，而 nginx 常驻占着 80：

```
ERROR:certbot._internal.renewal:Failed to renew certificate agent.mnb-lab.cn with error:
  Could not bind TCP port 80 because it is already in use by another process
  on this system (such as a web server).
certbot.errors.StandaloneBindError: Problem binding to port 80: [Errno 98] Address already in use
```

`certbot.timer` 每天跑 4 次（01:24 / 07:24 / 13:24 / 19:24），**连续失败 30 天，
没有任何可见信号** —— 错误只躺在 `/var/log/letsencrypt/letsencrypt.log` 里。
证书于 **2026-10-28 12:03:47** 到期。

### 第二层：明明有一张有效的、已覆盖 agent 的证书，却没用上

2026-09-02 就已签出一张 **SAN 覆盖三个域名** 的证书（`certbot certificates` 显示
`Domains: agent.mnb-lab.cn mnb-lab.cn www.mnb-lab.cn`，有效期到 2026-12-01），
但 nginx 的 **agent 443 block 仍指向**那条已废弃的独立 lineage
`/etc/nginx/ssl/agent.mnb-lab.cn/` ⇒ 一直在用一张本该弃用的证书。
（云端还留着 `default.conf.bak.certfix2.20260902` 备份 —— 就是那次"证书扩容"，
**只改了一半的 server block**。）

### 第三层：dry-run 才暴露 —— mnb-lab.cn 那条 lineage 其实也续不了

第一次 `certbot renew --cert-name mnb-lab.cn --dry-run` 报：

```
"detail": "60.205.93.8: Error reading HTTP response body: reader size limit exceeded"
Challenge failed for domain mnb-lab.cn
Challenge failed for domain www.mnb-lab.cn
```

**agent 的挑战没进失败名单**（说明第一层加的 webroot_map 改动是对的），
失败的是 mnb-lab.cn 与 www。真因：它们的 `:80` server block 是**裸的 server 级
`return 301`**，而 **nginx 的 server 级 return 在 rewrite 阶段执行、早于 location 匹配**
⇒ 挑战请求也被 301 到 https → 落到 SPA fallback → LE 读到的是 `index.html`
（几十 KB）⇒ 超过 LE 的响应体上限 ⇒ 挑战失败。

⇒ 若不修，**2026-11-01 起的那次续期同样会失败**，12-01 mnb-lab.cn 过期，
**两个站点一起挂**。（agent 的 `:80` block 一直是对的 —— **两个域名的 `:80` 写法
不一致，抄错就出事**。）

## 处置

1. **agent 443 block 重指向**：nginx 的 agent server block 改用
   `/etc/nginx/ssl/mnb-lab.cn/fullchain.pem`（那张 SAN 已覆盖 agent.mnb-lab.cn），
   `nginx -t` 通过后 reload。**零 ACME、零限额风险、立即生效。**
2. **mnb-lab.cn `:80` block 补挑战路径**：`location /.well-known/acme-challenge/
   { root /var/www/certbot; }`，并把 301 降级进 `location /`
   （server 级 return 会抢先于 location 匹配）。
3. **续期配置加固**：
   - `/etc/letsencrypt/renewal/mnb-lab.cn.conf` 的 `[[webroot_map]]` 补
     `agent.mnb-lab.cn = /var/www/certbot`（否则下次续期会把 agent 从 SAN 里**悄悄丢掉**），
     顺手修掉 `webroot_path` 值尾部的多余逗号；
   - 三条 lineage 全部加 `renew_hook = /etc/letsencrypt/renew-hook-nginx-reload.sh`
     （新脚本：`nginx -t && nginx -s reload`）。**原先没有 hook ⇒ 续期成功了
     nginx 也不换证书**。
4. **清理**：删除已过期的 agent lineage 与悬空的 `/etc/nginx/ssl/agent.mnb-lab.cn/`
   软链目录（nginx 已无引用），避免 timer 每 6 小时继续刷一条必然失败的日志、
   掩盖真实故障。
5. **仓库侧同步**：`nginx/conf.d/tunnel.conf` 是云端配置源
   （`scripts/deploy-auto.sh:273` 每次部署**无条件** `cp` 过去）⇒
   **只改云端会被下次部署冲回**，必须入库并推送。已 commit `0fde4fe37` 并推送。
6. **补上「可见告警」这一环**（类 20.220 / 20.239 的同族：失败只躺在日志里没人看）：
   新增 `.github/workflows/cert-expiry-check.yml` —— **每日**从公网探测
   ① 证书有效期（过期 / 剩余 <21 天 ⇒ 失败）
   ② `openssl x509 -checkhost` 验 SAN 是否真覆盖该主机名（抓"nginx 指向了另一条 lineage"）
   ③ ACME HTTP-01 挑战路径探针（期望 404；拿到 200/3xx ⇒ **下次续期必然失败**，
      正是本次第三层的判据）
   ⇒ **不需要任何 secret、不登录服务器、不改生产**，红叉直接落在仓库上。

## 附带发现：`mnb-lims.cn` 的证书根本没被用上（**已清理**）

- `mnb-lims.cn` / `www.mnb-lims.cn` 指向**同一个 IP**（60.205.93.8），但它的站点
  （`/etc/nginx/sites-available/lab-miniapp`）**在 `sites-enabled/` 里是空的 ⇒ 未启用**。
- 于是 Host 为 `mnb-lims.cn` 的请求落到 nginx 的**默认 443 server 块**
  （agent 的那个），拿到的是 **mnb-lab.cn 那张 SAN 证书** ——
  `openssl x509 -checkhost mnb-lims.cn` ⇒ **`does NOT match certificate`**（浏览器会报错）。
  certbot 里 mnb-lims 那条 lineage 有效期到 12-22，**却一张都没被服务端使用**。
- `certbot renew --cert-name mnb-lims.cn --dry-run` **失败**
  （`authenticator = nginx` 需要该站点存在才能做挑战）⇒ 11-22 那次续期同样会失败。
- ⇒ **主指挥裁定「清理掉」，2026-10-29 已执行**：
  1. **先备份**（删不可逆 ⇒ 留底）：`/root/cert-backup-20261029/mnb-lims.cn/`
     （全部历史 cert/chain/fullchain pem + renewal conf + 站点配置副本）。
  2. `certbot delete --cert-name mnb-lims.cn` ⇒ renewal 目录只剩 `mnb-lab.cn.conf`，
     **certbot.timer 不再有必然失败的续期**（此前每次都刷一条 ERROR）。
  3. 删除悬空的 `/etc/nginx/ssl/mnb-lims.cn/` 软链目录。
  4. **不动** `/etc/nginx/sites-available/lab-miniapp`（属 lab-miniapp 独立项目），
     只在文件头**加了一段 ASCII 警示注释**（正文逐字节未变，已与备份 diff 验证）：
     当前未启用、证书 lineage 已删、备份路径、**重新启用的三步**（先签证书 → 再软链 →
     nginx -t && reload），以及提醒它的 `:80` 是 server 级 `return 301` ⇒
     ACME 挑战会被 301 到 https ⇒ 续期失败（与本次 mnb-lab.cn 同款坑）。
  5. 体检 workflow 里把 `mnb-lims.cn` **移出检查范围**（它的证书已不存在，
     继续查只会读到默认 server 的证书 ⇒ 无意义结果）；并写明
     「若将来恢复该站点：先重新签发证书，再把域名加回 `FAIL_HOSTS`」。

⇒ 清理后状态：`certbot certificates` **只剩一条** `mnb-lab.cn`
（SAN 含 agent.mnb-lab.cn，到期 12-01），`/etc/letsencrypt/renewal/` 只剩
`mnb-lab.cn.conf`，`/etc/nginx/ssl/` 只剩 `mnb-lab.cn/`。
生产复验：`/health` `/` `/drive` 与 `https://mnb-lab.cn/` 全 200、`tls_verify=0`。

## 验证（全部走外部客户端，不看状态字段）

| 判据 | 结果 |
|---|---|
| 本机 `openssl s_client` | `notAfter=Dec 1 07:37:45 2026 GMT`，SAN = agent + mnb-lab.cn + www |
| 本机 `curl /health` `/` `/drive` | HTTP 200，`ssl_verify_result=0` |
| 本机 `curl https://mnb-lab.cn/` | HTTP 200，`ssl_verify_result=0` |
| 挑战路径直连 | `http://{mnb-lab.cn,www.mnb-lab.cn,agent.mnb-lab.cn}/.well-known/acme-challenge/<token>` 三个域名均 **200 且内容正确**；非挑战路径仍 301 到 https |
| `certbot renew --cert-name mnb-lab.cn --dry-run` | **all simulated renewals succeeded**，且输出 `Simulating renewal ... for agent.mnb-lab.cn and 2 more domains` ⇒ 续期后 agent 仍在 SAN 里 |
| `certbot renew --cert-name mnb-lims.cn --dry-run` | **失败**（该站点未启用 ⇒ nginx 插件做不了挑战）⇒ 见下方「附带发现」，**未处置** |
| `certbot certificates`（清理后） | 只剩 `mnb-lab.cn`（SAN 含 agent，到期 12-01）与 `mnb-lims.cn`（到期 12-22），**无过期 lineage** |
| 体检 workflow 脚本本地实跑 | RESULT: PASS；反向验证：`openssl x509 -checkhost` 对 SAN 不匹配的主机名**确实报 does NOT match** ⇒ 不是空转检查 |
| 部署后复验 | 云端 `/var/log/webhook-deploy.log` 末行「部署成功 ✓」，云端 repo HEAD == `0fde4fe37`，再测 `/health` `/` `/drive` 全 200 |

## 定位路径（下次照抄）

```bash
# 1) 先分清是"证书过期"还是"本机时钟不对"
date -u; echo | openssl s_client -connect agent.mnb-lab.cn:443 -servername agent.mnb-lab.cn \
  2>/dev/null | openssl x509 -noout -subject -dates -ext subjectAltName

# 2) 云端看 certbot 台账 (注意: "VALID" 不代表续期链路通)
ssh -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn 'certbot certificates'
ssh -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn \
  'grep -nE "Failed to renew|StandaloneBindError|reader size limit" /var/log/letsencrypt/letsencrypt.log | tail -20'

# 3) 看 nginx 实际指向哪条 lineage (别信配置注释, 看这行)
ssh -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn \
  'grep -n "ssl_certificate" /etc/nginx/conf.d/default.conf'

# 4) 唯一可信的判据 = dry-run (走 ACME staging, 不消耗生产限额)
ssh -i ~/.ssh/id_ed25519 root@agent.mnb-lab.cn 'certbot renew --cert-name <name> --dry-run'
```

## 沉淀

见 CLAUDE.md **类 20.239**（证书类判据必须用 dry-run；server 级 return 抢先于 location；
续期域名集来自 webroot_map；改云端 nginx 必须入库；续期后要挂 renew_hook；
续期失败要有可见告警）。
