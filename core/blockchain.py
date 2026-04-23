import sqlite3
import hashlib
import json
import os
import shutil
from datetime import datetime
from typing import List, Optional

class EnterpriseLedger:
    def __init__(self, db_path: str, image_dir: str):
        self.db_path = db_path
        self.image_dir = image_dir
        os.makedirs(self.image_dir, exist_ok=True)
        self.init_auth_db() # 确保用户表存在

    def init_auth_db(self):
        """初始化用户与权限管理表"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT,
                last_login DATETIME
            )
        """)
        # 预置一个演示用的超级管理员 (密码默认为 admin123)
        demo_pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                  ("admin", demo_pwd_hash, "SUPER_ADMIN", "系统管理员"))
        conn.commit()
        conn.close()

    def _get_file_hash(self, filepath: str) -> str:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _calculate_merkle_root(self, hash_list: List[str]) -> str:
        if not hash_list: 
            return hashlib.sha256(b"empty").hexdigest()
        if len(hash_list) == 1: 
            return hash_list[0]
        new_level = []
        for i in range(0, len(hash_list), 2):
            left = hash_list[i]
            right = hash_list[i+1] if i+1 < len(hash_list) else left
            combined = (left + right).encode('utf-8')
            new_level.append(hashlib.sha256(combined).hexdigest())
        return self._calculate_merkle_root(new_level)

    def get_last_hash(self) -> str:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT record_hash FROM records ORDER BY id DESC LIMIT 1")
        last_record = c.fetchone()
        conn.close()
        return last_record[0] if last_record else "GENESIS_BLOCK"

    def get_records(self, search_query="", category_filter="", page=1, per_page=10):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        query = "SELECT * FROM records WHERE category != 'SYSTEM'"
        count_query = "SELECT COUNT(*) FROM records WHERE category != 'SYSTEM'"
        params = []
        if category_filter:
            query += " AND category = ?"
            count_query += " AND category = ?"
            params.append(category_filter)
        if search_query:
            clause = " AND (item_name LIKE ? OR record_hash LIKE ? OR location LIKE ?)"
            query += clause
            count_query += clause
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
        c.execute(count_query, params)
        total_records = c.fetchone()[0]
        import math
        total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1
        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        c.execute(query, params)
        rows = [dict(row) for row in c.fetchall()]
        for row in rows:
            try:
                row['attachment_list'] = json.loads(row.get('attachments', '[]'))
            except:
                row['attachment_list'] = []
        conn.close()
        return rows, total_pages

    def get_categories(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM records WHERE category IS NOT NULL AND category != 'SYSTEM'")
        categories = [row[0] for row in c.fetchall()]
        conn.close()
        return categories

    def get_dashboard_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT note FROM records WHERE category = 'SYSTEM' AND item_name = 'STATUS_UPDATE'")
        consumed_hashes = set()
        for row in c.fetchall():
            if "[CONSUMED]" in row['note']:
                target = row['note'].split("[CONSUMED] ")[1].strip()
                consumed_hashes.add(target)
        c.execute("SELECT quantity, price, record_hash FROM records WHERE category != 'SYSTEM'")
        records = c.fetchall()
        active_records = [r for r in records if r['record_hash'] not in consumed_hashes]
        total_value = sum(r['quantity'] * r['price'] for r in active_records)
        total_items = sum(r['quantity'] for r in active_records)
        conn.close()
        return {
            "total_value": total_value,
            "total_items": total_items,
            "consumed_count": len(consumed_hashes),
            "consumed_hashes": list(consumed_hashes)
        }

    def add_asset_record(self, crypto_engine, **kwargs) -> str:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        previous_hash = self.get_last_hash()
        
        individual_hashes = []
        for path in kwargs.get('image_paths', []):
            img_hash = self._get_file_hash(path)
            individual_hashes.append(img_hash)
            prefix = img_hash[:2]
            shard_dir = os.path.join(self.image_dir, prefix)
            os.makedirs(shard_dir, exist_ok=True)
            shutil.copy(path, os.path.join(shard_dir, f"{img_hash}.jpg"))
            
        image_root_hash = self._calculate_merkle_root(individual_hashes)
        attachments_json = json.dumps(individual_hashes)
        timestamp = datetime.now().isoformat()
        
        # 🛡️ 数据规范化：确保存储和 hashing 的值完全一致
        # 我们这里不再强制转换为默认值，而是保留数据库原本的样子（空字符串就是空字符串）
        # 但我们要确保这些值被显式转为字符串
        safe_note = str(kwargs.get('note', ''))
        safe_location = str(kwargs.get('location', ''))
        safe_warranty = str(kwargs.get('warranty', ''))
        safe_expiry = str(kwargs.get('expiry', ''))
        
        data_fields = [
            kwargs.get('category'), 
            kwargs.get('name'), 
            kwargs.get('quantity'), 
            kwargs.get('price'), 
            safe_note, 
            timestamp, 
            previous_hash, 
            image_root_hash, 
            safe_location,
            safe_warranty, 
            safe_expiry
        ]
        
        data_string = "".join(map(str, data_fields))
        record_hash = hashlib.sha256(data_string.encode()).hexdigest()
        signature = crypto_engine.sign_data(record_hash)
        
        c.execute("""
            INSERT INTO records (
                category, item_name, quantity, price, note, timestamp, 
                previous_hash, image_hash, record_hash, signature,
                location, warranty_date, expiry_date, attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            kwargs.get('category'), kwargs.get('name'), kwargs.get('quantity'), 
            kwargs.get('price'), safe_note, timestamp, 
            previous_hash, image_root_hash, record_hash, signature,
            safe_location, safe_warranty, safe_expiry, attachments_json
        ))
        
        conn.commit()
        conn.close()
        return record_hash

    def update_asset_status(self, crypto_engine, target_hash: str, action: str = "CONSUMED"):
        dummy_path = os.path.join(self.image_dir, "system_action.jpg")
        if not os.path.exists(dummy_path):
            with open(dummy_path, "wb") as f: f.write(b"SYSTEM_ACTION")
        return self.add_asset_record(
            crypto_engine,
            category="SYSTEM",
            name="STATUS_UPDATE",
            quantity=0,
            price=0.0,
            note=f"[{action}] {target_hash}",
            image_paths=[dummy_path]
        )
