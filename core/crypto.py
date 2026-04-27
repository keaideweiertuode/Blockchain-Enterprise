import nacl.signing
import nacl.exceptions
import os
from typing import Optional

class EnterpriseCrypto:
    def __init__(self, public_key_path: str):
        self.public_key_path = public_key_path
        self._verify_key = None
        self._load_keys()

    def _load_keys(self):
        """初始加载公钥，服务器仅作防伪验签使用"""
        if os.path.exists(self.public_key_path):
            with open(self.public_key_path, "rb") as f:
                self._verify_key = nacl.signing.VerifyKey(f.read())

    def verify_signature(self, data_hash: str, signature_hex: str) -> bool:
        """使用公钥验证签名有效性"""
        if not self._verify_key:
            raise FileNotFoundError("🚨 找不到公钥，无法验证账本完整性！")
        
        try:
            self._verify_key.verify(data_hash.encode(), bytes.fromhex(signature_hex))
            return True
        except nacl.exceptions.BadSignatureError:
            return False
        except Exception:
            return False
