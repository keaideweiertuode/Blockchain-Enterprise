import os
import sys
import yaml
import random
import time

# 添加项目根目录到 PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.blockchain import EnterpriseLedger
from core.crypto import EnterpriseCrypto

def create_dummy_image(image_dir, prefix="dummy"):
    """创建临时测试图片并返回路径"""
    os.makedirs(image_dir, exist_ok=True)
    file_path = os.path.join(image_dir, f"{prefix}_{random.randint(1000, 9999)}.jpg")
    with open(file_path, "wb") as f:
        # 写入少量随机字节作为虚拟图片内容
        f.write(os.urandom(1024))
    return file_path

def generate_test_data(num_records=15):
    print(f"🚀 准备批量生成 {num_records} 条企业资产测试数据...")
    
    # 1. 加载配置
    config_path = os.path.join(BASE_DIR, "config", "settings.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    db_path = os.path.join(BASE_DIR, config['storage']['db_path'])
    image_dir = os.path.join(BASE_DIR, config['storage']['image_dir'])
    public_key_path = os.path.join(BASE_DIR, config['security']['public_key'])
    private_key_path = os.path.join(BASE_DIR, config['security']['private_key'])
    
    # 2. 初始化核心引擎
    ledger = EnterpriseLedger(db_path=db_path, image_dir=image_dir)
    
    # 注意：批量生成必须要有私钥才能签名
    crypto = EnterpriseCrypto(public_key_path, private_key_path)
    if not crypto.can_sign:
        print("❌ 错误：找不到管理员私钥，无法进行批量上链签名！")
        print(f"请检查路径: {private_key_path}")
        return

    # 3. 准备虚拟字典库
    categories = ["固定资产", "办公耗材", "数码设备", "研发设备"]
    items = {
        "固定资产": ["人体工学椅", "升降办公桌", "会议室白板", "文件柜"],
        "办公耗材": ["A4打印纸(箱)", "黑色碳素墨水", "得力中性笔(盒)", "订书机"],
        "数码设备": ["MacBook Pro M3", "ThinkPad T14", "Dell 27寸显示器", "iPad Pro"],
        "研发设备": ["NVIDIA A100 GPU", "树莓派开发板", "高精度示波器", "测试用iPhone"]
    }
    locations = ["A区办公区", "B区会议室", "C区研发实验室", "行政部仓库", "机房 Rack-03", "前台"]
    
    upload_temp_dir = os.path.join(BASE_DIR, "uploads")
    os.makedirs(upload_temp_dir, exist_ok=True)

    success_count = 0
    # 4. 开始批量上链
    for i in range(num_records):
        cat = random.choice(categories)
        name = random.choice(items[cat])
        qty = random.randint(1, 10)
        price = round(random.uniform(50.0, 15000.0), 2)
        loc = random.choice(locations)
        
        # 模拟生成 1-2 张附件图片
        dummy_images = [create_dummy_image(upload_temp_dir, f"test_{i}") for _ in range(random.randint(1, 2))]
        
        try:
            # 1. 准备数据
            prepared_data = ledger.prepare_asset_record(
                category=cat,
                name=name,
                quantity=qty,
                price=price,
                note=f"自动生成的测试资产 - 批次 {i}",
                location=loc,
                warranty="",
                expiry="",
                image_paths=dummy_images
            )
            
            record_hash = prepared_data['record_hash']
            payload = prepared_data['payload']
            
            # 2. 本地签名
            signature_hex = crypto.sign_data(record_hash)
            
            # 3. 提交上链
            final_hash = ledger.commit_asset_record(payload, signature_hex)
            
            print(f"[{i+1}/{num_records}] ✅ 上链成功: {name} (Hash: {final_hash[:8]}...)")
            success_count += 1

            
            # 清理临时文件
            for img in dummy_images:
                if os.path.exists(img): os.remove(img)
                
            # 稍微停顿，让 timestamp 具有明显的时间先后差异
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[{i+1}/{num_records}] ❌ 上链失败: {name} - 错误: {e}")

    print("-" * 50)
    print(f"🎉 批量生成完成！共成功添加 {success_count} 条记录。")
    print("您可以登录网页端查看最新生成的资产列表及仪表盘统计。")

if __name__ == "__main__":
    generate_test_data(25) # 默认生成 25 条
