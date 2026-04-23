import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, Dict, List

class EnterpriseAuth:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        """获取数据库连接并开启 WAL 模式"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username, password) -> Optional[Dict]:
        """验证用户名密码，返回用户信息"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        pwd_hash = self._hash_password(password)
        c.execute("SELECT id, username, role, full_name FROM users WHERE username = ? AND password_hash = ?", 
                  (username, pwd_hash))
        user = c.fetchone()
        
        if user:
            # 更新最后登录时间
            c.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user['id']))
            conn.commit()
            user_dict = dict(user)
            conn.close()
            return user_dict
        
        conn.close()
        return None

    def create_user(self, username, password, role, full_name=""):
        """创建新用户 (仅超级管理员可用)"""
        conn = self._get_conn()
        c = conn.cursor()
        pwd_hash = self._hash_password(password)
        try:
            c.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                      (username, pwd_hash, role, full_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_all_users(self) -> List[Dict]:
        """获取系统所有用户列表"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, username, role, full_name, last_login FROM users ORDER BY id ASC")
        users = [dict(row) for row in c.fetchall()]
        conn.close()
        return users

    def delete_user(self, user_id: int) -> bool:
        """删除指定用户 (禁止自杀式删除)"""
        conn = self._get_conn()
        c = conn.cursor()
        try:
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
