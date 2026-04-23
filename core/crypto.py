import nacl.signing
import nacl.exceptions
import os
from typing import Optional

class EnterpriseCrypto:
    def __init__(self, public_key_path: str, private_key_path: Optional[str] = None):
        self.public_key_path = public_key_path
        self.private_key_path = private_key_path
        self._verify_key = None
        self._signing_key = None
        self._load_keys()

    def _load_keys(self):
        """初始加载公钥，私钥为可选加载"""
        # 加载公钥（审计者必须具备）
        if os.path.exists(self.public_key_path):
            with open(self.public_key_path, "rb") as f:
                self._verify_key = nacl.signing.VerifyKey(f.read())
        
        # 加载私钥（仅管理员具备）
        if self.private_key_path and os.path.exists(self.private_key_path):
            with open(self.private_key_path, "rb") as f:
                self._signing_key = nacl.signing.SigningKey(f.read())

    @property
    def can_sign(self) -> bool:
        """检查当前实例是否具备签发权限"""
        return self._signing_key is not None

    def sign_data(self, data_hash: str) -> str:
        """使用私钥对哈希进行数字签名"""
        if not self._signing_key:
            raise PermissionError("🚨 当前权限为[审计员]，无法执行签发操作！请加载私钥。")
        
        signature = self._signing_key.sign(data_hash.encode()).signature
        return signature.hex()

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

    def reload_private_key(self, private_key_path: str):
        """动态加载私钥，支持物理隔离场景（如插上U盘后加载）"""
        if os.path.exists(private_key_path):
            with open(private_key_path, "rb") as f:
                self._signing_key = nacl.signing.SigningKey(f.read())
            self.private_key_path = private_key_path
            return True
        return False
