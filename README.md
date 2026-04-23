# 🛡️ Blockchain Enterprise (企业级资产审计平台)

**Blockchain Enterprise** 是从个人版 (v0.4) 演进出的工业级资产审计与管理平台。它将区块链的不可篡改性与企业级的权限管理、物理级安全规范深度结合，提供一套高可信的资产全生命周期追踪方案。

---

## 🚀 核心企业级特性

### 1. 🔐 多角色访问控制 (RBAC)
系统内置了完善的角色权限体系，通过 Session 级中间件强制校验用户身份：
*   **SUPER_ADMIN (超级管理员)**：拥有全权，负责用户管理及系统核心配置。
*   **MANAGER (资产管理员)**：负责实物资产录入、状态更新。**必须持有物理私钥才能执行操作**。
*   **AUDITOR (审计员)**：拥有全局只读权限，负责生成并签署正式审计报告、执行全链校验。
*   **VIEWER (普通员工)**：仅能查看资产列表及空间位置，无法访问敏感哈希或审计后台。

### 2. 🔌 物理级“冷钱包”签名模式
本项目实现了极致的物理安全隔离（Air-gapped Readiness）：
*   **动态私钥重载**：系统支持将 `private.key` 存储在加密 U 盘中。
*   **插拔式录入**：平时系统处于“只读审计”状态（Key Offline）。仅在录入新资产时插入 U 盘并点击“加载物理钥匙”，系统才会将私钥载入内存。
*   **表单锁定机制**：当物理钥匙未识别时，资产录入表单将自动置灰锁定，杜绝任何未经授权的写入尝试。

### 3. 📜 自动化合规审计
*   **合规评分系统**：一键执行全链扫描，根据哈希链连续性、签名有效性输出 0-100 的直观评分。
*   **正式审计报告**：生成带有唯一 **Report ID**、时间戳及密码学验签明细的 HTML 报告（可另存为 PDF）。
*   **哈希一致性加固**：采用严格的数据规范化逻辑，确保选填字段留空时依然能保持 100% 的校验准确率。

### 4. 📝 结构化审计日志
实时记录所有关键操作至 `storage/audit.log`：
*   记录 **[执行用户]**、**[来源 IP]**、**[操作路径]** 及 **[结果]**。
*   所有非法越权尝试及系统异常均会被永久追溯。

---

## 🛠️ 安装与运行

### 1. 环境准备
```bash
# 进入项目目录
cd blockchain-enterprise
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
# 安装依赖
pip install -r requirements.txt
```

### 2. 初始化账号
系统预置了超级管理员账号：
*   **用户名**：`admin`
*   **密码**：`admin123`

如需创建员工账号，请运行：
```bash
python3 -c "from core.auth import EnterpriseAuth; auth = EnterpriseAuth('database/ledger.db'); auth.create_user('username', 'password', 'VIEWER', '姓名')"
```

### 3. 配置物理私钥路径
在 `config/settings.yaml` 中配置您的 U 盘路径：
```yaml
security:
  private_key: "/media/ian/YOUR_USB_NAME/private.key" 
```

### 4. 启动服务
```bash
export PYTHONPATH=$PYTHONPATH:.
python api/main.py
```
访问：`http://localhost:8080`

---

## 📄 许可证
本项目采用 MIT 许可证。建议用于对数据真实性有极高要求的企业资产盘点与合规场景。
