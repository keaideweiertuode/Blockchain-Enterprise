import os
import logging
from flask import request, jsonify, redirect
from datetime import datetime

class EnterpriseMiddleware:
    def __init__(self, app, crypto_engine, log_file):
        self.app = app
        self.crypto = crypto_engine
        self.log_file = log_file
        self._setup_logger()

    def _setup_logger(self):
        """配置企业级审计日志器"""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        self.logger = logging.getLogger("EnterpriseAudit")
        self.logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        fh = logging.FileHandler(self.log_file)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(client_ip)s] [%(role)s] %(message)s'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def register(self):
        """将中间件挂载到 Flask 生命周期"""
        
        @self.app.before_request
        def before_request_func():
            # 1. 公开路径豁免 (允许访问登录、健康检查、静态资源、物品图片)
            public_paths = ['/login', '/health', '/static', '/images']
            if any(request.path.startswith(p) for p in public_paths):
                return

            # 2. 身份认证检查 (检查 Session)
            from flask import session
            user = session.get('user')
            if not user:
                # 如果是 API 请求返回 JSON，否则重定向到登录页
                if request.path.startswith('/api') or request.path.startswith('/admin'):
                    return jsonify({"status": "error", "message": "Unauthorized"}), 401
                return redirect('/login')

            # 3. 角色与 IP 信息注入日志
            client_ip = request.remote_addr
            current_role = user.get('role', 'VIEWER')
            
            # 4. 权限校验 (RBAC)
            # ADMIN 路径仅限 SUPER_ADMIN 和已加载私钥的 MANAGER
            if request.path.startswith('/admin'):
                allowed_roles = ['SUPER_ADMIN', 'MANAGER']
                if current_role not in allowed_roles or (current_role == 'MANAGER' and not self.crypto.can_sign):
                    self.logger.warning(
                        f"Insufficient permissions: {current_role} tried to access {request.path}",
                        extra={'client_ip': client_ip, 'role': current_role}
                    )
                    return jsonify({
                        "status": "forbidden",
                        "message": "🚨 权限不足：当前操作需要资产管理员(MANAGER)权限并加载私钥。"
                    }), 403

            # 5. 审计日志 (记录修改类操作、审计操作或全链校验)
            if request.method != 'GET' or 'audit' in request.path or 'verify' in request.path:
                self.logger.info(
                    f"User: {user['username']} | Method: {request.method} | Path: {request.path}",
                    extra={'client_ip': client_ip, 'role': current_role}
                )

    def log_custom_event(self, event_type, message):
        """允许业务逻辑手动触发审计日志"""
        client_ip = request.remote_addr if request else "SYSTEM"
        role = "ADMIN" if self.crypto.can_sign else "AUDITOR"
        self.logger.info(
            f"[{event_type}] {message}",
            extra={'client_ip': client_ip, 'role': role}
        )
