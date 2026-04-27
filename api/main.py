import os
import yaml
from flask import Flask, request, jsonify, session, redirect
from core.blockchain import EnterpriseLedger
from core.crypto import EnterpriseCrypto
from core.auditor import EnterpriseAuditor
from core.auth import EnterpriseAuth
from api.routes import register_routes
from api.middleware import EnterpriseMiddleware

# 1. 加载配置
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "../config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.yaml")
with open(CONFIG_PATH, 'r') as f:
    config = yaml.safe_load(f)

# 设置基础路径 (绝对路径)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 将配置中的相对路径转换为绝对路径
DB_PATH = os.path.join(BASE_DIR, config['storage']['db_path'])
IMAGE_DIR = os.path.join(BASE_DIR, config['storage']['image_dir'])
PUBLIC_KEY_PATH = os.path.join(BASE_DIR, config['security']['public_key'])
LOG_FILE = os.path.join(BASE_DIR, config['server']['log_file'])

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = os.urandom(24)

# 2. 初始化核心引擎 (使用绝对路径)
crypto = EnterpriseCrypto(
    public_key_path=PUBLIC_KEY_PATH
)

ledger = EnterpriseLedger(
    db_path=DB_PATH,
    image_dir=IMAGE_DIR
)

auth = EnterpriseAuth(
    db_path=DB_PATH
)

auditor = EnterpriseAuditor(
    db_path=DB_PATH,
    crypto_engine=crypto
)

# 3. 注册企业审计中间件
middleware = EnterpriseMiddleware(
    app=app, 
    crypto_engine=crypto, 
    log_file=LOG_FILE
)
middleware.register()

# --- 全局错误处理器 ---
@app.errorhandler(403)
def forbidden_error(e):
    return jsonify({"status": "error", "code": 403, "message": "Access Denied"}), 403

@app.errorhandler(404)
def not_found_error(e):
    return jsonify({"status": "error", "code": 404, "message": "Resource Not Found"}), 404

@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_unexpected_error(e):
    middleware.log_custom_event("SYSTEM_ERROR", str(e))
    return jsonify({
        "status": "fail",
        "code": 500,
        "message": "Internal Server Error"
    }), 500

# 4. 注册业务路由
# 注意：我们将绝对路径后的配置传给路由，或者直接传配置
# 为了让路由里的 send_from_directory 拿到绝对路径，我们更新 config
config['storage']['image_dir_abs'] = IMAGE_DIR
config['storage']['db_path_abs'] = DB_PATH
config['storage']['upload_temp_dir_abs'] = os.path.join(BASE_DIR, config['storage']['upload_temp_dir'])

register_routes(app, ledger, crypto, auditor, auth, config)

# 5. 基础健康检查
@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "mode": "Administrator" if crypto.can_sign else "Auditor",
        "user": session.get('user', {}).get('username', 'anonymous'),
        "base_dir": BASE_DIR
    })

if __name__ == "__main__":
    app.run(
        host=config['server']['host'],
        port=config['server']['port'],
        debug=config['server']['debug']
    )
