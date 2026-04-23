import os
import hashlib
import nacl.signing
from mnemonic import Mnemonic

def recover_keys():
    print("🛡️  Blockchain Ledger 最高权限恢复程序")
    print("-" * 50)
    print("⚠️ 警告：此操作将覆盖现有的 keys 文件夹内容。")
    words = input("🔑 请输入您的 12 个助记词（全部小写，用单个空格隔开）:\n> ").strip()

    mnemo = Mnemonic("english")
    
    # 验证助记词是否是合法的 BIP39 格式
    if not mnemo.check(words):
        print("\n❌ 恢复失败：助记词无效！请检查是否有拼写错误或多余的空格。")
        return

    print("\n⏳ 正在通过 BIP39 协议进行哈希降维推导...")
    
    # 1. 从助记词推导种子 (Seed)
    seed = mnemo.to_seed(words, passphrase="")
    
    # 2. 压缩为 32 字节，并生成 PyNaCl 的 Ed25519 密钥对
    seed_32 = hashlib.sha256(seed).digest()
    signing_key = nacl.signing.SigningKey(seed_32)
    verifying_key = signing_key.verify_key

    # 3. 保存恢复出来的密钥
    os.makedirs("keys", exist_ok=True)
    with open("keys/private.key", "wb") as f:
        f.write(signing_key.encode())
    with open("keys/public.key", "wb") as f:
        f.write(verifying_key.encode())

    print("-" * 50)
    print("✅ 浴火重生！恢复成功！")
    print("您的 private.key 和 public.key 已被精准还原，并保存在 keys/ 目录下。")
    print("系统已重新获得最高控制权，您可以继续登记和验证物品了。")

if __name__ == "__main__":
    recover_keys()