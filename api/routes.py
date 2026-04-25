import os
import io
import csv
import qrcode
from flask import request, jsonify, send_from_directory, flash, redirect, render_template, Response, send_file, session, url_for
from datetime import datetime

def register_routes(app, ledger, crypto, auditor, auth, config):
    
    # 获取绝对路径配置
    IMAGE_DIR = config['storage']['image_dir_abs']
    UPLOAD_TEMP_DIR = config['storage']['upload_temp_dir_abs']
    DB_PATH = config['storage']['db_path_abs']

    # --- 身份认证路由 ---
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            user = auth.authenticate(username, password)
            if user:
                # 检查角色是否需要强制 2FA
                if user['role'] in ['SUPER_ADMIN', 'MANAGER']:
                    session['pre_2fa_user'] = user
                    if not user.get('totp_secret'):
                        return redirect(url_for('setup_2fa'))
                    else:
                        return redirect(url_for('verify_2fa'))
                else:
                    session['user'] = user
                    flash(f"欢迎回来, {user['full_name']}!", "success")
                    return redirect(url_for('index'))
            else:
                flash("用户名或密码错误", "danger")
        return render_template("login.html")

    @app.route("/login/setup_2fa", methods=["GET", "POST"])
    def setup_2fa():
        pre_user = session.get('pre_2fa_user')
        if not pre_user:
            return redirect(url_for('login'))
        
        if request.method == "POST":
            token = request.form.get("token")
            secret = session.get('temp_totp_secret')
            if auth.verify_totp(secret, token):
                if auth.set_user_totp_secret(pre_user['id'], secret):
                    # 登录成功
                    pre_user['totp_secret'] = secret
                    session['user'] = session.pop('pre_2fa_user')
                    session.pop('temp_totp_secret', None)
                    flash(f"2FA 设置成功！欢迎回来, {pre_user['full_name']}!", "success")
                    return redirect(url_for('index'))
                else:
                    flash("保存密钥失败，请重试", "danger")
            else:
                flash("动态验证码错误，请重新输入", "danger")
                
            # POST 失败时，返回原有的 secret 和 QR 码
            secret = session.get('temp_totp_secret')
            import pyotp
            import base64
            totp = pyotp.TOTP(secret)
            uri = totp.provisioning_uri(name=pre_user['username'], issuer_name='Blockchain Enterprise')
            img = qrcode.make(uri)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            return render_template("setup_2fa.html", qr_b64=qr_b64, secret=secret)
                
        # GET 请求生成新密钥和 QR 码
        import pyotp
        import base64
        if 'temp_totp_secret' not in session:
            session['temp_totp_secret'] = auth.generate_totp_secret()
            
        secret = session['temp_totp_secret']
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=pre_user['username'], issuer_name='Blockchain Enterprise')
        
        # 生成二维码的 Base64 字符串
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        return render_template("setup_2fa.html", qr_b64=qr_b64, secret=secret)

    @app.route("/login/verify_2fa", methods=["GET", "POST"])
    def verify_2fa():
        pre_user = session.get('pre_2fa_user')
        if not pre_user:
            return redirect(url_for('login'))
            
        if request.method == "POST":
            token = request.form.get("token")
            secret = pre_user.get('totp_secret')
            if auth.verify_totp(secret, token):
                session['user'] = session.pop('pre_2fa_user')
                flash(f"验证成功！欢迎回来, {pre_user['full_name']}!", "success")
                return redirect(url_for('index'))
            else:
                flash("动态验证码错误", "danger")
                
        return render_template("verify_2fa.html")

    @app.route("/logout")
    def logout():
        session.pop('user', None)
        flash("您已成功退出登录", "info")
        return redirect(url_for('login'))

    # --- Web 前端界面渲染 ---
    @app.route("/")
    def index():
        search = request.args.get("search", "")
        category = request.args.get("category", "")
        page = request.args.get("page", 1, type=int)
        per_page = config['business'].get('pagination_size', 6)
        
        records, total_pages = ledger.get_records(search, category, page, per_page)
        categories = ledger.get_categories()
        dash_data = ledger.get_dashboard_stats()
        
        return render_template(
            "index.html", 
            records=records, 
            categories=categories, 
            current_search=search, 
            current_category=category, 
            current_page=page, 
            total_pages=total_pages, 
            dash_data=dash_data,
            user=session.get('user'),
            crypto_can_sign=crypto.can_sign
        )

    # --- 资产读取接口 ---
    @app.route("/api/assets", methods=["GET"])
    def list_assets():
        search = request.args.get("search", "")
        category = request.args.get("category", "")
        page = request.args.get("page", 1, type=int)
        per_page = config['business'].get('pagination_size', 10)
        
        records, total_pages = ledger.get_records(search, category, page, per_page)
        return jsonify({
            "records": records,
            "total_pages": total_pages,
            "current_page": page
        })

    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        return jsonify(ledger.get_dashboard_stats())

    @app.route("/api/categories", methods=["GET"])
    def get_categories():
        return jsonify(ledger.get_categories())

    # --- 用户管理路由 (仅限 SUPER_ADMIN) ---
    @app.route("/admin/users")
    def manage_users():
        if session.get('user', {}).get('role') != 'SUPER_ADMIN':
            flash("权限不足：仅系统管理员可进入用户管理", "danger")
            return redirect(url_for('index'))
        
        users = auth.get_all_users()
        return render_template("users.html", users=users, current_user=session.get('user'))

    @app.route("/admin/users/add", methods=["POST"])
    def add_user():
        if session.get('user', {}).get('role') != 'SUPER_ADMIN':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        full_name = request.form.get("full_name")
        
        if auth.create_user(username, password, role, full_name):
            flash(f"用户 {username} 创建成功", "success")
        else:
            flash(f"用户创建失败：用户名可能已存在", "danger")
        return redirect(url_for('manage_users'))

    @app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
    def delete_user(user_id):
        if session.get('user', {}).get('role') != 'SUPER_ADMIN':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        
        # 禁止删除自己
        if user_id == session.get('user', {}).get('id'):
            flash("错误：不能注销当前登录的管理员账号", "danger")
            return redirect(url_for('manage_users'))

        if auth.delete_user(user_id):
            flash("用户已成功注销", "warning")
        else:
            flash("注销失败", "danger")
        return redirect(url_for('manage_users'))

    # --- 资产管理接口 (需要私钥) ---
    @app.route("/add", methods=["POST"])
    @app.route("/admin/assets/add", methods=["POST"])
    def add_asset():
        try:
            category = request.form["category"]
            name = request.form["name"]
            quantity = int(request.form["quantity"])
            price = float(request.form["price"])
            note = request.form.get("note", "")
            location = request.form.get("location", "未标记")
            warranty = request.form.get("warranty", "")
            expiry = request.form.get("expiry", "")
            
            files = request.files.getlist("images")
            os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)
            saved_paths = []
            
            for file in files:
                if file and file.filename != "":
                    temp_path = os.path.join(UPLOAD_TEMP_DIR, file.filename)
                    file.save(temp_path)
                    saved_paths.append(temp_path)

            if not saved_paths:
                flash("至少需要上传一张图片!", "danger")
                return redirect(url_for('index'))

            record_hash = ledger.add_asset_record(
                crypto,
                category=category,
                name=name,
                quantity=quantity,
                price=price,
                note=note,
                location=location,
                warranty=warranty,
                expiry=expiry,
                image_paths=saved_paths
            )
            
            for p in saved_paths:
                if os.path.exists(p): os.remove(p)

            flash(f"已录入! Hash: {record_hash[:16]}...", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for('index'))

    @app.route("/consume/<record_hash>", methods=["POST"])
    @app.route("/admin/assets/consume/<record_hash>", methods=["POST"])
    def consume_asset(record_hash):
        try:
            ledger.update_asset_status(crypto, record_hash, "CONSUMED")
            flash("状态已更新为已消耗/售出", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            return redirect(url_for('index'))

    # --- 审计与工具接口 ---
    @app.route("/verify_chain")
    def verify_chain():
        try:
            results = auditor.run_full_audit()
            report = auditor.generate_compliance_report()
            
            if report['score'] == 100:
                flash("Blockchain verified! 所有记录安全且未被篡改。", "success")
            else:
                flash(f"警告：账本校验未通过！合规评分: {report['score']}%", "danger")
                for r in results:
                    if not r["valid"]:
                        flash(f"Block {r['id']} ({r['item_name']}) 异常: {', '.join(r['issues'])}", "danger")
            return redirect(url_for('index'))
        except FileNotFoundError as e:
            flash(str(e), "danger")
            return redirect(url_for('index'))

    @app.route("/audit/summary")
    def get_audit_summary():
        return jsonify(auditor.generate_compliance_report())

    @app.route("/audit/report")
    def get_audit_report():
        try:
            report_data = auditor.generate_compliance_report()
            return render_template("audit_report.html", report=report_data)
        except FileNotFoundError as e:
            flash(str(e), "danger")
            return redirect(url_for('index'))

    @app.route("/qr/<record_hash>")
    def generate_qr(record_hash):
        img = qrcode.make(f"Ledger Hash:\n{record_hash}")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')

    @app.route("/export")
    def export_csv():
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute("SELECT * FROM records ORDER BY id ASC")
        rows = c.fetchall()
        column_names = [description[0] for description in c.description]
        conn.close()

        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(column_names)
        cw.writerows(rows)
        return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=ledger.csv"})

    @app.route("/admin/crypto/reload", methods=["POST"])
    def reload_key():
        # 仅限 MANAGER 和 SUPER_ADMIN
        if session.get('user', {}).get('role') not in ['SUPER_ADMIN', 'MANAGER']:
            return jsonify({"status": "error", "message": "权限不足"}), 403
            
        success = crypto.reload_private_key(config['security']['private_key'])
        if success:
            flash("✅ 物理私钥已识别，签名功能已激活！", "success")
        else:
            flash("❌ 无法找到物理私钥，请检查 U 盘是否插入或路径是否正确。", "danger")
        return redirect(url_for('index'))

    # --- 附件服务接口 ---
    @app.route("/images/<filename>")
    def get_image(filename):
        # 处理系统占位图
        if filename == "system_action.jpg":
            return send_from_directory(IMAGE_DIR, filename)
        
        # 处理哈希分片图
        prefix = filename[:2]
        shard_dir = os.path.join(IMAGE_DIR, prefix)
        return send_from_directory(shard_dir, filename)
