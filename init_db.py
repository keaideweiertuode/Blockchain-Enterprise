import sqlite3
import os

def init_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect("database/ledger.db")
    c = conn.cursor()
    
    # 创建包含 0.4 完整字段的新表
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
    print("✅ 数据库 (v0.4 结构) 初始化完成！")

if __name__ == "__main__":
    init_db()