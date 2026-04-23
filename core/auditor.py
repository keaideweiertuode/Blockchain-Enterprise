import sqlite3
import hashlib
from typing import List, Dict
from core.crypto import EnterpriseCrypto

class EnterpriseAuditor:
    def __init__(self, db_path: str, crypto_engine: EnterpriseCrypto):
        self.db_path = db_path
        self.crypto = crypto_engine

    def run_full_audit(self) -> List[Dict]:
        """执行全账本深度审计"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM records ORDER BY id ASC")
        records = c.fetchall()
        conn.close()

        audit_results = []
        previous_hash = "GENESIS_BLOCK"

        for r in records:
            report = {
                "id": r['id'],
                "item_name": r['item_name'],
                "valid": True,
                "issues": []
            }

            # 1. 验证链条连续性
            if r['previous_hash'] != previous_hash:
                report["valid"] = False
                report["issues"].append(f"链条断裂: 期望 {previous_hash[:8]}, 实际 {r['previous_hash'][:8]}")

            # 🛡️ 2. 验证内容哈希 (必须与 blockchain.py 的逻辑完全一致)
            # 这里的原则是：直接使用数据库中的原始字符串值，不要尝试补全默认值
            # 因为 blockchain.py 现在确保存储和 hashing 都是原始值。
            data_fields = [
                r['category'],
                r['item_name'],
                r['quantity'],
                r['price'],
                str(r['note']) if r['note'] is not None else "",
                r['timestamp'],
                r['previous_hash'],
                r['image_hash'],
                str(r['location']) if r['location'] is not None else "",
                str(r['warranty_date']) if r['warranty_date'] is not None else "",
                str(r['expiry_date']) if r['expiry_date'] is not None else ""
            ]
            
            data_string = "".join(map(str, data_fields))
            calculated_hash = hashlib.sha256(data_string.encode()).hexdigest()

            if calculated_hash != r['record_hash']:
                report["valid"] = False
                report["issues"].append("数据完整性破坏: 内容与指纹不符")

            # 3. 验证身份签名
            sig_valid = self.crypto.verify_signature(r['record_hash'], r['signature'])
            if not sig_valid:
                report["valid"] = False
                report["issues"].append("签名验证失败: 非法签发者或篡改攻击")

            audit_results.append(report)
            previous_hash = r['record_hash']

        return audit_results

    def generate_compliance_report(self) -> Dict:
        """生成全局合规性评分与审计摘要"""
        from datetime import datetime
        import uuid
        
        results = self.run_full_audit()
        total_blocks = len(results)
        
        if total_blocks == 0:
            return {
                "score": 100, 
                "status": "EMPTY", 
                "message": "账本为空，处于待录入状态。",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "report_id": str(uuid.uuid4())[:8].upper()
            }

        invalid_blocks = [r for r in results if not r['valid']]
        valid_count = total_blocks - len(invalid_blocks)
        
        compliance_score = int((valid_count / total_blocks) * 100)
        
        issue_categories = {
            "chain_break": 0,
            "data_tamper": 0,
            "signature_fail": 0
        }
        
        for r in invalid_blocks:
            for issue in r['issues']:
                if "链条断裂" in issue: issue_categories["chain_break"] += 1
                elif "数据完整性" in issue: issue_categories["data_tamper"] += 1
                elif "签名验证" in issue: issue_categories["signature_fail"] += 1

        return {
            "score": compliance_score,
            "total_records": total_blocks,
            "valid_records": valid_count,
            "tampered_records": len(invalid_blocks),
            "issue_breakdown": issue_categories,
            "health_status": "EXCELLENT" if compliance_score == 100 else ("WARNING" if compliance_score > 80 else "CRITICAL"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report_id": "REP-" + datetime.now().strftime("%Y%m%d") + "-" + str(uuid.uuid4())[:4].upper(),
            "details": results
        }
