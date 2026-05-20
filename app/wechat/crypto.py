"""企业微信消息加解密"""

import base64
import hashlib
import struct
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class WXBizMsgCrypt:
    """企业微信消息加解密类"""

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        # EncodingAESKey 是 Base64 编码的 43 字符，解码后 32 字节
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        self.iv = self.aes_key[:16]

    def _pkcs7_pad(self, data: bytes) -> bytes:
        """PKCS7 填充"""
        block_size = 32
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    def _pkcs7_unpad(self, data: bytes) -> bytes:
        """PKCS7 去填充"""
        pad_len = data[-1]
        return data[:-pad_len]

    def _sha1_sign(self, *args) -> str:
        """SHA1 签名"""
        sorted_args = sorted(args)
        return hashlib.sha1("".join(sorted_args).encode("utf-8")).hexdigest()

    def verify_url(self, signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        """
        URL 验证（企业微信后台配置回调时调用）

        Returns:
            解密后的 echostr，应原样返回给企业微信
        """
        # 验证签名
        expected = self._sha1_sign(self.token, timestamp, nonce, echostr)
        if expected != signature:
            raise ValueError("签名验证失败")

        # 解密 echostr
        return self._decrypt(echostr)

    def decrypt_msg(self, post_data: str, signature: str, timestamp: str, nonce: str) -> dict:
        """
        解密回调消息

        Args:
            post_data: POST 请求体（XML 字符串）
            signature: URL 参数中的 msg_signature
            timestamp: URL 参数中的 timestamp
            nonce: URL 参数中的 nonce

        Returns:
            解密后的消息字典
        """
        import xml.etree.ElementTree as ET

        root = ET.fromstring(post_data)
        encrypt_elem = root.find("Encrypt")
        if encrypt_elem is None:
            # 尝试带命名空间查找
            for child in root:
                if child.tag.endswith("Encrypt") or child.tag == "Encrypt":
                    encrypt_elem = child
                    break
        if encrypt_elem is None:
            raise ValueError(f"XML 中未找到 Encrypt 元素，XML 内容: {post_data[:500]}")
        encrypt = encrypt_elem.text

        # 验证签名
        expected = self._sha1_sign(self.token, timestamp, nonce, encrypt)
        if expected != signature:
            raise ValueError("消息签名验证失败")

        # 解密
        xml_content = self._decrypt(encrypt)

        # 解析 XML
        msg_root = ET.fromstring(xml_content)
        msg = {}
        for child in msg_root:
            msg[child.tag] = child.text
        return msg

    def encrypt_msg(self, reply_msg: str, nonce: str, timestamp: str) -> str:
        """
        加密回复消息

        Args:
            reply_msg: 回复内容（XML 字符串）
            nonce: 随机字符串
            timestamp: 时间戳

        Returns:
            加密后的 XML 字符串
        """
        encrypt = self._encrypt(reply_msg)
        signature = self._sha1_sign(self.token, timestamp, nonce, encrypt)

        return f"""<xml>
<Encrypt><![CDATA[{encrypt}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""

    def _encrypt(self, text: str) -> str:
        """AES 加密"""
        data = text.encode("utf-8")
        # 16 字节随机 + 4 字节长度 + 内容 + corp_id
        random_prefix = secrets.token_bytes(16)
        msg_len = struct.pack("!I", len(data))
        plaintext = random_prefix + msg_len + data + self.corp_id.encode("utf-8")
        plaintext = self._pkcs7_pad(plaintext)

        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        return base64.b64encode(ciphertext).decode("utf-8")

    def _decrypt(self, encrypted: str) -> str:
        """AES 解密"""
        ciphertext = base64.b64decode(encrypted)

        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv), backend=default_backend())
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        plaintext = self._pkcs7_unpad(plaintext)

        # 解析：16 字节随机 + 4 字节长度 + 内容 + corp_id
        msg_len = struct.unpack("!I", plaintext[16:20])[0]
        content = plaintext[20:20 + msg_len]

        return content.decode("utf-8")
