"""recovery_code_service — 用户自助重置密码恢复码 (2026-09-02)

背景: agent 曾静默修改用户密码, 用户被锁死只能找管理员重置。
本服务提供"恢复码"能力, 让用户丢失密码时完全自助、不经过任何人工:

- 用户能正常登录时, 在【设置 → 账号安全】生成恢复码 (明文仅显示一次, 自行保存)
- 密码丢失时, 在登录页输入 用户名 + 恢复码 + 新密码, 一步完成重置

安全设计:
- DB 只存 SHA-256 哈希 (members.recovery_code_hash), 明文不落库
- 码字母表去除易混淆字符 (0/o/1/i/l), 12 位 ≈ 60 bit 熵, 抗在线爆破 (配合限流)
- 单次使用: 重置成功后 hash 置 NULL, 需重新生成
- 输入归一化: 去分隔符/空格 + lower, 用户手抄格式不敏感
- 接口限流: pwreset_limiter 5 次/15 分钟 (app/core/rate_limit.py)
"""
import hashlib
import hmac
import secrets

from app.models.base import utcnow

# 32 字符无易混淆字母表 → 12 位码 = 32^12 ≈ 2^60 组合
_CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
_CODE_LENGTH = 12
_CODE_GROUP = 4  # 每 4 位一组显示: abcd-efgh-jkmn


def generate_recovery_code() -> str:
    """生成 12 位恢复码明文, 分组显示 'abcd-efgh-jkmn'"""
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    return "-".join(raw[i:i + _CODE_GROUP] for i in range(0, _CODE_LENGTH, _CODE_GROUP))


def normalize_recovery_code(code: str) -> str:
    """输入归一化: 去空格/横线等分隔符 + lower"""
    return "".join(ch for ch in (code or "").lower() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    """SHA-256 hex 摘要 (码本身高熵, 无需 bcrypt 慢哈希)"""
    return hashlib.sha256(normalize_recovery_code(code).encode("utf-8")).hexdigest()


def verify_recovery_code(code: str, stored_hash: str) -> bool:
    """常数时间比较, 防时序侧信道"""
    return hmac.compare_digest(hash_recovery_code(code), stored_hash or "")


def rotate_member_recovery_code(member) -> str:
    """为 member 生成新恢复码 (轮换旧码), 存哈希, 返回明文 (仅此一次)

    调用方负责 commit。生成时间记录在 recovery_code_generated_at (naive UTC)。
    """
    code = generate_recovery_code()
    member.recovery_code_hash = hash_recovery_code(code)
    member.recovery_code_generated_at = utcnow()
    return code


def clear_member_recovery_code(member) -> None:
    """重置成功后清空恢复码 (单次有效) — 调用方负责 commit"""
    member.recovery_code_hash = None
    member.recovery_code_generated_at = None
