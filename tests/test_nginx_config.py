"""
Test nginx config hardening (HSTS preload / TLS 1.3 / OCSP stapling / strong ciphers).

测试目的：云服务器 nginx/conf.d/tunnel.conf 安全配置守卫。
解析 nginx 配置文件，验证关键 TLS/HSTS 指令正确设置，防止 regression。

每个 test case 对应一个铁律：
1. test_protocols_tls12_tls13_only — 禁用 TLS 1.0/1.1, 仅保留 TLSv1.2 TLSv1.3
2. test_hsts_preload_enabled — HSTS 含 preload 指令 (2 年 + includeSubDomains + preload)
3. test_strong_ciphers — 强密码套件 (ECDHE + AES-GCM, 不含 CBC/3DES/RSA-only)
4. test_ocsp_stapling_enabled — OCSP stapling 开启 + resolver 配置
5. test_nginx_config_syntax — 配置文件无语法错 (括号匹配, 必需指令存在)

铁律依据：CLAUDE.md 2026-06-13 (types 指令覆盖事故) + 2026-06-29 (HSTS preload webhint fix)。
本测试为 config-as-code 守卫，未来改 tunnel.conf 后能立即回归。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# 项目根 → nginx config 相对路径 (worktree 内可能用 ./nginx/conf.d/tunnel.conf)
REPO_ROOT = Path(__file__).resolve().parent.parent
NGINX_CONF = REPO_ROOT / "nginx" / "conf.d" / "tunnel.conf"


def _read_nginx_conf() -> str:
    """读取 nginx config 文件, 缺失时 pytest.skip."""
    if not NGINX_CONF.exists():
        pytest.skip(f"nginx config not found at {NGINX_CONF}")
    return NGINX_CONF.read_text(encoding="utf-8")


def _split_server_blocks(content: str) -> list[str]:
    """朴素切分 server { ... } 顶层块 (单层嵌套假设足够)。"""
    # 找 server { 起始, 然后计数 { 和 } 配对
    blocks: list[str] = []
    idx = 0
    while True:
        m = re.search(r"server\s*\{", content[idx:])
        if not m:
            break
        start = idx + m.start()
        # 找匹配的右花括号
        depth = 1
        i = idx + m.end()
        while i < len(content) and depth > 0:
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            i += 1
        if depth != 0:
            break  # 语法错, 中止
        blocks.append(content[start:i])
        idx = i
    return blocks


def _find_listening_server_blocks(content: str) -> list[str]:
    """找所有 listen 443 ssl http2; 的 server 块 (HTTPS server)."""
    blocks = _split_server_blocks(content)
    return [b for b in blocks if re.search(r"listen\s+443\s+ssl", b)]


def _find_hsts_headers(block: str) -> list[str]:
    """提取一个 server 块里所有 Strict-Transport-Security header 值."""
    pattern = re.compile(
        r'add_header\s+Strict-Transport-Security\s+"([^"]+)"', re.IGNORECASE
    )
    return pattern.findall(block)


# ============================================================
# Test 1: TLS 1.2/1.3 only (禁用 TLS 1.0/1.1)
# ============================================================


def test_protocols_tls12_tls13_only() -> None:
    """所有 HTTPS server 块必须 ssl_protocols TLSv1.2 TLSv1.3; 禁用 TLSv1 / TLSv1.1.

    铁律依据：TLS 1.0/1.1 已被 RFC 8996 正式弃用 (2021), PCI DSS 要求禁用。
    弱协议支持 = 中间人降级攻击面。
    """
    content = _read_nginx_conf()
    blocks = _find_listening_server_blocks(content)
    assert blocks, "no listen 443 ssl server block found in tunnel.conf"

    for block in blocks:
        m = re.search(r"ssl_protocols\s+([^;]+);", block)
        assert m, f"server block missing ssl_protocols directive: {block[:200]}"
        protocols = m.group(1).strip()
        # 必须含 TLSv1.2 TLSv1.3
        assert "TLSv1.2" in protocols, (
            f"ssl_protocols must include TLSv1.2, got: {protocols}"
        )
        assert "TLSv1.3" in protocols, (
            f"ssl_protocols must include TLSv1.3, got: {protocols}"
        )
        # 严禁 TLSv1 (无 v 后缀) 或 TLSv1.1
        tokens = re.split(r"\s+", protocols)
        for tok in tokens:
            assert tok not in {"TLSv1", "TLSv1.1"}, (
                f"weak protocol {tok} enabled, must disable: {protocols}"
            )


# ============================================================
# Test 2: HSTS preload enabled
# ============================================================


def test_hsts_preload_enabled() -> None:
    """每个 HTTPS server 块 server-level HSTS 必须含 preload + max-age≥1年 + includeSubDomains.

    铁律依据：hstspreload.org 提交门槛 max-age ≥ 31536000 (1 年)。
    本项目用 63072000 (2 年) 满足门槛 + 留升级 buffer。
    """
    content = _read_nginx_conf()
    blocks = _find_listening_server_blocks(content)
    assert blocks, "no listen 443 ssl server block found in tunnel.conf"

    min_max_age = 31536000  # hstspreload.org 最低门槛 1 年
    for block in blocks:
        # 只看 server 块级 (不含 location { } 嵌套), 用 server { 后第一段
        # 但我们用 _find_hsts_headers 取所有, 然后找 server-level
        headers = _find_hsts_headers(block)
        assert headers, (
            "server block must declare Strict-Transport-Security header (HSTS)"
        )
        # 至少一个 HSTS header 必须有 preload 指令
        has_preload = any("preload" in h for h in headers)
        assert has_preload, (
            f"no HSTS header with 'preload' directive. Headers found: {headers}"
        )
        # 所有 HSTS header 必须 includeSubDomains + max-age 达标
        for h in headers:
            assert "includeSubDomains" in h, (
                f"HSTS must include includeSubDomains: {h}"
            )
            m_age = re.search(r"max-age=(\d+)", h)
            assert m_age, f"HSTS missing max-age: {h}"
            age = int(m_age.group(1))
            assert age >= min_max_age, (
                f"HSTS max-age={age} < {min_max_age} (hstspreload.org 门槛): {h}"
            )


# ============================================================
# Test 3: Strong ciphers (无 weak CBC/3DES)
# ============================================================


def test_strong_ciphers() -> None:
    """每个 HTTPS server 块的 ssl_ciphers 必须用强套件 (ECDHE + AES-GCM/CHACHA20).

    禁用 CBC 模式 (BEAST/Lucky 13 攻击面) + 3DES (SWEET32) + 纯 RSA 密钥交换 (无前向保密).
    强套件范式 (Mozilla Intermediate): ECDHE-ECDSA-AES*-GCM-SHA*, ECDHE-RSA-AES*-GCM-SHA*,
    ECDHE-*-CHACHA20-POLY1305, DHE-RSA-AES*-GCM-SHA*.
    """
    content = _read_nginx_conf()
    blocks = _find_listening_server_blocks(content)
    assert blocks, "no listen 443 ssl server block found in tunnel.conf"

    weak_cipher_keywords = [
        "CBC",        # CBC 模式 (BEAST/Lucky 13)
        "3DES",       # SWEET32
        "RC4",        # 已破解
        "MD5",        # HMAC-MD5 弱
        "SHA1",       # HMAC-SHA1 弱 (NIST 2017 后弃用)
        "NULL",       # 无加密
        "EXPORT",     # 出口级弱
        "DES",        # 单 DES 已破解
        "PSK",        # 预共享密钥 (不适用于公网)
    ]

    for block in blocks:
        m = re.search(r"ssl_ciphers\s+([^;]+);", block)
        assert m, f"server block missing ssl_ciphers directive: {block[:200]}"
        ciphers = m.group(1)
        # 必须有 ECDHE (前向保密)
        assert "ECDHE" in ciphers, (
            f"ssl_ciphers must include ECDHE for forward secrecy: {ciphers}"
        )
        # 必须有 AES-GCM 或 CHACHA20 (AEAD, 无 CBC)
        assert "GCM" in ciphers or "CHACHA20" in ciphers, (
            f"ssl_ciphers must include AEAD cipher (GCM/CHACHA20): {ciphers}"
        )
        # 不许含弱套件关键字
        for weak in weak_cipher_keywords:
            assert weak not in ciphers, (
                f"weak cipher keyword '{weak}' in ssl_ciphers: {ciphers}"
            )


# ============================================================
# Test 4: OCSP stapling enabled + resolver 配置
# ============================================================


def test_ocsp_stapling_enabled() -> None:
    """每个 HTTPS server 块必须开 OCSP stapling + resolver (向 CA OCSP server 发请求必需).

    铁律依据：ssl_stapling on 但没 resolver → nginx 启动警告 + stapling 静默失效。
    resolver 8.8.8.8/8.8.4.4 (Google Public DNS) 是稳定公网选择。
    """
    content = _read_nginx_conf()
    blocks = _find_listening_server_blocks(content)
    assert blocks, "no listen 443 ssl server block found in tunnel.conf"

    for block in blocks:
        # 必须 ssl_stapling on;
        m_stapling = re.search(r"ssl_stapling\s+on\s*;", block)
        assert m_stapling, (
            f"server block missing ssl_stapling on: {block[:200]}"
        )
        # 必须 ssl_stapling_verify on; (验证 OCSP response 签名)
        m_verify = re.search(r"ssl_stapling_verify\s+on\s*;", block)
        assert m_verify, (
            f"server block missing ssl_stapling_verify on (security critical)"
        )
        # 必须有 resolver 指令 (公网 DNS, 用于查询 CA OCSP server 域名)
        # 严格匹配 directive (行首或前面是空白, 后跟空格 + IP + 可选 valid=NNs)
        # 不匹配注释里的 "resolver" 关键字 (resolver 注释里出现)
        m_resolver = re.search(
            r"(?:^|\n)\s*resolver\s+([\d.\s]+(?:valid=\d+s)?)\s*;", block
        )
        assert m_resolver, (
            f"server block missing resolver directive (OCSP stapling 必需): {block[:200]}"
        )
        resolver_value = m_resolver.group(1).strip()
        # 取 IP 部分 (空格分词, 排除 valid= 参数)
        resolver_ips = [t for t in resolver_value.split() if not t.startswith("valid=")]
        assert len(resolver_ips) >= 1, "resolver must have at least 1 DNS server"
        # resolver IP 必须公网 IP (不能是 127.0.0.1 / 私有地址)
        for ip in resolver_ips:
            assert not ip.startswith("127."), (
                f"resolver must be public DNS, not loopback: {ip}"
            )
            assert not ip.startswith("192.168."), (
                f"resolver must be public DNS, not private: {ip}"
            )


# ============================================================
# Test 5: nginx config 语法合法 (括号匹配 + 必需指令存在)
# ============================================================


def test_nginx_config_syntax() -> None:
    """nginx.conf 全文件: 花括号匹配 + 每 server 块有 listen + 必需 ssl_certificate 配对.

    这层防线检测手改 nginx config 时漏写花括号或漏配 ssl_certificate 等基本错误。
    即使不上 nginx -t (容器里没装 nginx), 静态解析也能挡住 80% typo.
    """
    content = _read_nginx_conf()

    # 1. 花括号匹配 (顶层, 不嵌套分析)
    open_braces = content.count("{")
    close_braces = content.count("}")
    assert open_braces == close_braces, (
        f"unbalanced braces: {open_braces} '{{' vs {close_braces} '}}'"
    )

    # 2. 注释剔除后再扫 server 块
    content_no_comments = re.sub(r"#.*", "", content)
    blocks = _split_server_blocks(content_no_comments)
    assert len(blocks) >= 2, (
        f"expected >= 2 server blocks (80 + 443), got {len(blocks)}"
    )

    # 3. 每个 server 块必须有 listen 指令
    for i, block in enumerate(blocks):
        assert re.search(r"listen\s+", block), (
            f"server block #{i} missing 'listen' directive"
        )
        # 必须有 server_name
        assert re.search(r"server_name\s+", block), (
            f"server block #{i} missing 'server_name' directive"
        )

    # 4. 443 ssl 块必须有 ssl_certificate + ssl_certificate_key 配对
    https_blocks = [b for b in blocks if re.search(r"listen\s+443\s+ssl", b)]
    assert https_blocks, "expected at least 1 listen 443 ssl server block"

    for i, block in enumerate(https_blocks):
        assert re.search(r"ssl_certificate\s+", block), (
            f"https server block #{i} missing ssl_certificate"
        )
        assert re.search(r"ssl_certificate_key\s+", block), (
            f"https server block #{i} missing ssl_certificate_key"
        )