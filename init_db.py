import os
import yaml
import sqlite3

def init_db():
    print("🛠️ 正在初始化 Blockchain Enterprise 数据库...")
    
    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), "config", "settings.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    db_path = config['storage']['db_path']
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. 创建资产记录表 (records)
    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            item_name TEXT,
            quantity INTEGER,
            price REAL,
            note TEXT,
            timestamp TEXT,
            previous_hash TEXT,
            image_hash TEXT,
            record_hash TEXT,
            signature TEXT,
            location TEXT DEFAULT '未标记',
            warranty_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            attachments TEXT DEFAULT '[]'
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # 2. 触发 EnterpriseLedger 的初始化 (自动创建 users 表和默认 admin)
    from core.blockchain import EnterpriseLedger
    image_dir = config['storage']['image_dir']
    ledger = EnterpriseLedger(db_path=db_path, image_dir=image_dir)
    
    print("✅ 数据库与表结构 (records, users) 已初始化完成！")

if __name__ == "__main__":
    # 为了能导入 core 模块
    import sys
    sys.path.append(os.path.dirname(__file__))
    init_db()
