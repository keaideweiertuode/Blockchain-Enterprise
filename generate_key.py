import os
from mnemonic import Mnemonic
import hashlib
import nacl.signing

def generate_bip39_keys():
    os.makedirs("keys", exist_ok=True)
    
    # 1. 生成 12 个单词的 BIP39 助记词
    mnemo = Mnemonic("english")
    words = mnemo.generate(strength=128)
    
    # 2. 从助记词推导种子 (Seed)
    seed = mnemo.to_seed(words, passphrase="")
    
    # 3. 使用种子的前 32 字节通过 PyNaCl 生成 Ed25519 密钥对
    seed_32 = hashlib.sha256(seed).digest()
    signing_key = nacl.signing.SigningKey(seed_32)
    verifying_key = signing_key.verify_key
    
    with open("keys/private.key", "wb") as f:
        f.write(signing_key.encode())
    with open("keys/public.key", "wb") as f:
        f.write(verifying_key.encode())
        
    print("✅ 密钥生成成功！")
    print("🚨 【极其重要】请将以下 12 个单词抄写在纸上并安全保管！")
    print("-" * 50)
    print(f"🔑 助记词: {words}")
    print("-" * 50)
    print("只要拥有这 12 个单词，您就能在任何设备上恢复账本的最高权限。")

if __name__ == "__main__":
    generate_bip39_keys()