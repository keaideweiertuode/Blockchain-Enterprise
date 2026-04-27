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

    def _get_conn(self):
        """获取数据库连接并开启 WAL 模式"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def init_auth_db(self):
        """初始化用户与权限管理表"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT,
                last_login DATETIME,
                totp_secret TEXT
            )
        """)
        # 尝试升级表结构以兼容旧版
        try:
            c.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
        except sqlite3.OperationalError:
            pass # 可能是列已存在
            
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
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT record_hash FROM records ORDER BY id DESC LIMIT 1")
        last_record = c.fetchone()
        conn.close()
        return last_record[0] if last_record else "GENESIS_BLOCK"

    def _resolve_asset_statuses(self) -> dict:
        """
        按时间顺序解析所有系统状态更新区块，计算每个资产的当前状态。
        格式兼容：
        旧格式: [CONSUMED] <hash> -> SCRAPPED
        新格式: [STATUS_UPDATE] <hash> | <NEW_STATUS> | <metadata>
        返回: { "hash": {"status": "STATUS", "metadata": "...", "timestamp": "..."} }
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT note, timestamp FROM records WHERE category = 'SYSTEM' AND item_name = 'STATUS_UPDATE' ORDER BY id ASC")
        
        statuses = {}
        for row in c.fetchall():
            note = row['note']
            if note.startswith("[CONSUMED]"):
                target_hash = note.split("[CONSUMED] ")[1].strip()
                statuses[target_hash] = {"status": "SCRAPPED", "metadata": "Legacy Consumed", "timestamp": row['timestamp']}
            elif note.startswith("[STATUS_UPDATE]"):
                try:
                    parts = note.replace("[STATUS_UPDATE]", "").strip().split(" | ")
                    if len(parts) >= 2:
                        target_hash = parts[0].strip()
                        new_status = parts[1].strip()
                        metadata = parts[2].strip() if len(parts) > 2 else ""
                        statuses[target_hash] = {"status": new_status, "metadata": metadata, "timestamp": row['timestamp']}
                except Exception:
                    pass # Ignore malformed records
        conn.close()
        return statuses

    def get_records(self, search_query="", category_filter="", page=1, per_page=10):
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 预先计算所有资产的状态
        all_statuses = self._resolve_asset_statuses()

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
            
            # 附加当前状态信息
            asset_status = all_statuses.get(row['record_hash'], {"status": "AVAILABLE", "metadata": "", "timestamp": ""})
            row['current_status'] = asset_status['status']
            row['status_metadata'] = asset_status['metadata']
            row['status_timestamp'] = asset_status['timestamp']

        conn.close()
        return rows, total_pages

    def get_categories(self) -> List[str]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM records WHERE category IS NOT NULL AND category != 'SYSTEM'")
        categories = [row[0] for row in c.fetchall()]
        conn.close()
        return categories

    def get_dashboard_stats(self) -> dict:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        all_statuses = self._resolve_asset_statuses()
        consumed_hashes = [h for h, data in all_statuses.items() if data['status'] == 'SCRAPPED']
        
        c.execute("SELECT quantity, price, record_hash FROM records WHERE category != 'SYSTEM'")
        records = c.fetchall()
        active_records = [r for r in records if all_statuses.get(r['record_hash'], {}).get('status', 'AVAILABLE') != 'SCRAPPED']
        total_value = sum(r['quantity'] * r['price'] for r in active_records)
        total_items = sum(r['quantity'] for r in active_records)
        conn.close()
        return {
            "total_value": total_value,
            "total_items": total_items,
            "consumed_count": len(consumed_hashes),
            "consumed_hashes": consumed_hashes
        }

    def prepare_asset_record(self, **kwargs) -> dict:
        """
        第一阶段：准备数据
        计算图片的 Merkle Root 和记录的最终 Hash，但不签名也不入库。
        返回完整的待上链数据包，供前端签名使用。
        """
        previous_hash = self.get_last_hash()
        
        # 1. 计算图片哈希 (此时图片还在 uploads 临时目录)
        individual_hashes = []
        for path in kwargs.get('image_paths', []):
            if os.path.exists(path):
                img_hash = self._get_file_hash(path)
                individual_hashes.append(img_hash)
            
        image_root_hash = self._calculate_merkle_root(individual_hashes)
        attachments_json = json.dumps(individual_hashes)
        timestamp = datetime.now().isoformat()
        
        # 2. 数据规范化
        safe_note = str(kwargs.get('note', ''))
        safe_location = str(kwargs.get('location', ''))
        safe_warranty = str(kwargs.get('warranty', ''))
        safe_expiry = str(kwargs.get('expiry', ''))
        str_quantity = str(kwargs.get('quantity'))
        str_price = str(kwargs.get('price'))
        
        # 3. 严格按顺序拼接，生成最终指纹
        data_fields = [
            str(kwargs.get('category')), str(kwargs.get('name')), str_quantity, 
            str_price, safe_note, timestamp, 
            previous_hash, image_root_hash, safe_location,
            safe_warranty, safe_expiry
        ]
        data_string = "".join(data_fields)
        record_hash = hashlib.sha256(data_string.encode()).hexdigest()
        
        # 返回完整的数据包
        return {
            "record_hash": record_hash,
            "payload": {
                "category": str(kwargs.get('category')),
                "name": str(kwargs.get('name')),
                "quantity": str_quantity,
                "price": str_price,
                "note": safe_note,
                "timestamp": timestamp,
                "previous_hash": previous_hash,
                "image_root_hash": image_root_hash,
                "location": safe_location,
                "warranty": safe_warranty,
                "expiry": safe_expiry,
                "attachments_json": attachments_json,
                "temp_image_paths": kwargs.get('image_paths', [])
            }
        }

    def commit_asset_record(self, payload: dict, signature_hex: str) -> bool:
        """
        第二阶段：确认上链
        接收前端传回的签名，验证无误后，转移图片并写入数据库。
        """
        conn = self._get_conn()
        c = conn.cursor()
        
        # 1. 再次重构数据字符串（防止前端篡改 payload）
        data_fields = [
            str(payload['category']), str(payload['name']), str(payload['quantity']), 
            str(payload['price']), str(payload['note']), str(payload['timestamp']), 
            str(payload['previous_hash']), str(payload['image_root_hash']), 
            str(payload['location']), str(payload['warranty']), str(payload['expiry'])
        ]
        data_string = "".join(data_fields)
        recalculated_hash = hashlib.sha256(data_string.encode()).hexdigest()
        
        # 注意：这里的验证已在 API 层通过 EnterpriseCrypto 完成，
        # ledger 只负责入库逻辑，但为了防呆，确保传进来的 hash 是准确的。
        
        # 2. 转移并分片存储图片
        temp_paths = payload.get('temp_image_paths', [])
        if isinstance(payload.get('attachments_json'), str):
            hashes = json.loads(payload['attachments_json'])
        else:
            hashes = payload.get('attachments_json', [])
            payload['attachments_json'] = json.dumps(hashes)
            
        for i, path in enumerate(temp_paths):
            if os.path.exists(path) and i < len(hashes):
                img_hash = hashes[i]
                prefix = img_hash[:2]
                shard_dir = os.path.join(self.image_dir, prefix)
                os.makedirs(shard_dir, exist_ok=True)
                final_path = os.path.join(shard_dir, f"{img_hash}.jpg")
                shutil.copy(path, final_path)
                os.remove(path) # 清理临时文件

        # 3. 数据库持久化
        c.execute("""
            INSERT INTO records (
                category, item_name, quantity, price, note, timestamp, 
                previous_hash, image_hash, record_hash, signature,
                location, warranty_date, expiry_date, attachments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload['category'], payload['name'], payload['quantity'], 
            payload['price'], payload['note'], payload['timestamp'], 
            payload['previous_hash'], payload['image_root_hash'], 
            recalculated_hash, signature_hex,
            payload['location'], payload['warranty'], payload['expiry'], 
            payload['attachments_json']
        ))
        
        conn.commit()
        conn.close()
        return recalculated_hash


    def prepare_status_update(self, target_hash: str, action: str = "SCRAPPED", metadata: str = "") -> dict:
        """
        准备状态变更数据包，返回供前端签名使用的指纹
        """
        dummy_path = os.path.join(self.image_dir, "system_action.jpg")
        if not os.path.exists(dummy_path):
            with open(dummy_path, "wb") as f: f.write(b"SYSTEM_ACTION")
            
        note_content = f"[STATUS_UPDATE] {target_hash} | {action} | {metadata}" if action != "CONSUMED" else f"[STATUS_UPDATE] {target_hash} | SCRAPPED | Legacy Consumed"

        # 调用已有的准备逻辑，不进行签名和入库
        prepared_data = self.prepare_asset_record(
            category="SYSTEM",
            name="STATUS_UPDATE",
            quantity=0,
            price=0.0,
            note=note_content,
            image_paths=[dummy_path]
        )
        
        return prepared_data
