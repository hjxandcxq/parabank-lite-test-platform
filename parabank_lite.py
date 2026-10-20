# -*- coding: utf-8 -*-
"""ParaBank Lite — 被测银行系统 (Flask Blueprint)"""
import os
import random
import re
import secrets
import sqlite3
import time
from flask import (Blueprint, Response, jsonify, render_template, request,
                   redirect, url_for, session)
from werkzeug.security import generate_password_hash, check_password_hash

pb_bp = Blueprint('parabank', __name__,
                  template_folder='templates/parabank')

# 项目根目录 = 本文件所在目录（Windows / Linux 通用）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'parabank_test.db')

USERNAME_RE = re.compile(r'^[A-Za-z0-9_]+$')
PASSWORD_RE = re.compile(r'^[A-Za-z0-9@#$_\.]+$')
AMOUNT_RE = re.compile(r'^-?[\d.]*$')

# ============================================================
# 登录图形验证码（扩展功能）
# 验证码以 SVG 图片呈现，4 位字母数字（去掉易混淆的 0/O/1/I），
# 不区分大小写，有效期 PB_CAPTCHA_TTL 秒（默认 120），提交一次即作废。
#
# 自动化测试取码：GET /parabank/captcha/text 返回当前会话的验证码文本，
# 仅在 PB_CAPTCHA_TEST_HOOK=1（默认开启）时可用。该接口是测试专用后门，
# 面向手工演示/生产演示时可设 PB_CAPTCHA_TEST_HOOK=0 关闭——关闭后自动化
# 登录用例会因拿不到验证码而失败。
# ============================================================
CAPTCHA_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
CAPTCHA_LENGTH = 4
CAPTCHA_TTL = int(os.environ.get('PB_CAPTCHA_TTL', '120'))
CAPTCHA_TEST_HOOK = os.environ.get('PB_CAPTCHA_TEST_HOOK', '1') == '1'

# ============================================================
# 注入缺陷（演示用）：BUG-01 ~ BUG-03。
# 登记表见 testcase_spec.INJECTED_DEFECTS，每个缺陷都注明它违反文档的哪条
# 规则、预期让哪几条用例失败。置为 False 即恢复"完全符合文档"的系统，
# 51 条用例应当全绿。
# ============================================================
INJECT_DEFECTS = True

# 提示文案与校验顺序严格对齐《ParaBank Lite 业务规则与测试用例设计（最新版）》
# 与三张模块用例表的"预期结果"列，pytest 套件按同一文案断言。


def validate_login(username, password):
    if not username:
        return False, '用户名必填'
    if not (6 <= len(username) <= 20):
        return False, '用户名长度6-20位'
    if not USERNAME_RE.match(username):
        return False, '用户名只能包含字母、数字和下划线'
    if not password:
        return False, '密码必填'
    if not (6 <= len(password) <= 20):
        return False, '密码长度6-20位'
    if not PASSWORD_RE.match(password):
        return False, '密码只允许字母、数字和字符@#$._'
    return True, None


def validate_captcha(captcha_input, expected, issued_at=None, now=None):
    """校验图形验证码（纯函数，便于一致性校验回放）。

    校验顺序：非空 → 会话中是否存在/是否过期 → 是否一致（忽略大小写）。
    issued_at / now 同时传入时才做有效期检查。
    """
    value = (captcha_input or '').strip()
    if not value:
        return False, '验证码必填'
    if not expected:
        return False, '验证码已失效，请刷新'
    if issued_at is not None and now is not None and now - issued_at > CAPTCHA_TTL:
        return False, '验证码已失效，请刷新'
    if value.upper() != expected.upper():
        return False, '验证码错误'
    return True, None


def new_captcha():
    """生成新验证码并写入会话（同时刷新签发时间）。"""
    text = ''.join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_LENGTH))
    session['pb_captcha'] = text
    session['pb_captcha_ts'] = time.time()
    return text


def captcha_expired():
    ts = session.get('pb_captcha_ts')
    return ts is None or (time.time() - ts) > CAPTCHA_TTL


def _captcha_svg(text):
    """把验证码画成带干扰线/噪点的 SVG（不依赖 Pillow 等第三方图形库）。"""
    width, height = 120, 40
    rnd = random.Random()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#f5f8ff"/>',
    ]
    for _ in range(6):
        parts.append(
            f'<line x1="{rnd.randint(0, width)}" y1="{rnd.randint(0, height)}" '
            f'x2="{rnd.randint(0, width)}" y2="{rnd.randint(0, height)}" '
            f'stroke="#c3d3ee" stroke-width="1"/>')
    for _ in range(24):
        parts.append(
            f'<circle cx="{rnd.randint(0, width)}" cy="{rnd.randint(0, height)}" '
            f'r="{rnd.randint(1, 2)}" fill="#d5e1f5"/>')
    for i, ch in enumerate(text):
        x = 14 + i * 26
        y = 29 + rnd.randint(-3, 3)
        angle = rnd.randint(-18, 18)
        color = rnd.choice(['#1a3d7c', '#2f5fa8', '#0f6b5c', '#7a3b8f'])
        parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="24" font-weight="bold" fill="{color}" '
            f'transform="rotate({angle} {x} {y})">{ch}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def validate_register(username, password, confirm):
    if not username:
        return False, '用户名必填'
    if not (6 <= len(username) <= 20):
        return False, '用户名长度6-20位'
    if not USERNAME_RE.match(username):
        return False, '用户名只能包含字母、数字和下划线'
    if not password:
        return False, '密码必填'
    if not (6 <= len(password) <= 20):
        return False, '密码长度6-20位'
    if not PASSWORD_RE.match(password):
        return False, '密码只能包含字母、数字和@#$._'
    if not (re.search(r'[A-Za-z]', password) and re.search(r'\d', password)):
        return False, '密码必须包含字母和数字'
    if password != confirm:
        return False, '两次密码不一致'
    return True, None


def validate_transfer(amount_str, from_acc, to_acc):
    if not amount_str or not amount_str.strip():
        return False, None, '转账金额不能为空'
    s = amount_str.strip()
    if not AMOUNT_RE.match(s):
        return False, None, '只能输入数字和小数点'
    # BUG-03：漏做"仅允许一个小数点"校验（违反规则 2.3(4)，
    #         预期 TRAN_11 的提示变成"金额最多保留2位小数"）
    if s.count('.') > 1 and not INJECT_DEFECTS:
        return False, None, '仅允许一个小数点'
    body = s[1:] if s.startswith('-') else s
    if body in ('', '.') or body.startswith('.'):
        return False, None, '请输入有效金额'
    if '.' in body and len(body.split('.', 1)[1]) > 2:
        return False, None, '金额最多保留2位小数'
    try:
        amount = float(s)
    except ValueError:
        return False, None, '请输入有效金额'
    if amount <= 0:
        return False, None, '金额必须大于0'
    # BUG-02：上限边界判断写成"≥ 50000 即超限"（违反规则 2.3(2)，
    #         预期边界值 50000.00 的 TRAN_05 失败）
    if amount > 50000 or (INJECT_DEFECTS and amount == 50000):
        return False, None, '单笔金额不能超过50000元'
    if from_acc and to_acc and from_acc == to_acc:
        return False, None, '源账户和目标账户不能相同'
    return True, amount, None


def get_db():
    # timeout：平台与测试进程同时读写同一个库时等待锁
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


# 预置演示数据（与 testcase_spec.PRESET_USERS 保持一致，check_consistency.py 会校验）
# alice01：测试主账号 —— 登录与转账用例的合规账号，持有转账账户
#          A=10001（初始 100000.00）、B=10002（0.00）、C=10003（100.00）
# admin：文档「系统定义」里的初始账号，不持有账户
PRESET_USERS = [
    {'username': 'alice01', 'password': 'Pass123',
     'accounts': [('10001', 100000.00), ('10002', 0.00), ('10003', 100.00)]},
    {'username': 'admin', 'password': 'admin123', 'accounts': []},
]

DEMO_NOT_EXIST_ACCOUNT = '99999'


def _ensure_tables():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS pb_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS pb_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        account_number TEXT UNIQUE NOT NULL,
        balance REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS pb_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_account TEXT,
        to_account TEXT,
        amount REAL,
        txn_type TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


def reset_demo_data():
    """恢复预置演示数据：预置账号与余额复位，清空测试新增的账号与交易流水。

    套件执行前调用（conftest.py 的 autouse fixture），保证用例前置条件可重复：
    - 账户 A（10001）余额 100000.00（TRAN_005 需 ≥ 50000）
    - 账户 B（10002）余额 0.00，作为正常目标账户
    - 账户 C（10003）余额 100.00（TRAN_016 余额不足、TRAN_017 余额等于转账金额）
    - 账户 D（99999）不存在（TRAN_019 目标账户不存在）
    - 预置账号 alice01 / admin 就位，其余账号与流水一律清掉
    """
    _ensure_tables()
    conn = get_db()
    c = conn.cursor()

    names = [u['username'] for u in PRESET_USERS]
    marks = ','.join('?' * len(names))
    c.execute(f'DELETE FROM pb_accounts WHERE user_id NOT IN '
              f'(SELECT id FROM pb_users WHERE username IN ({marks}))', names)
    c.execute(f'DELETE FROM pb_users WHERE username NOT IN ({marks})', names)

    for user in PRESET_USERS:
        row = c.execute('SELECT id FROM pb_users WHERE username=?',
                        (user['username'],)).fetchone()
        if row:
            uid = row['id']
            c.execute('UPDATE pb_users SET password_hash=? WHERE id=?',
                      (generate_password_hash(user['password']), uid))
        else:
            c.execute('INSERT INTO pb_users (username, password_hash) VALUES (?, ?)',
                      (user['username'], generate_password_hash(user['password'])))
            uid = c.lastrowid

        # 清掉该预置账号名下多余的账户（例如注册流程给它留下的 0 元账户）
        if user['accounts']:
            keep = ','.join('?' * len(user['accounts']))
            c.execute(f'DELETE FROM pb_accounts WHERE user_id=? '
                      f'AND account_number NOT IN ({keep})',
                      [uid] + [acc for acc, _ in user['accounts']])
        else:
            c.execute('DELETE FROM pb_accounts WHERE user_id=?', (uid,))

        for acc_no, balance in user['accounts']:
            exists = c.execute('SELECT id FROM pb_accounts WHERE account_number=?',
                               (acc_no,)).fetchone()
            if exists:
                c.execute('UPDATE pb_accounts SET user_id=?, balance=? '
                          'WHERE account_number=?', (uid, balance, acc_no))
            else:
                c.execute('INSERT INTO pb_accounts (user_id, account_number, balance) '
                          'VALUES (?, ?, ?)', (uid, acc_no, balance))

    c.execute('DELETE FROM pb_transactions')
    conn.commit()
    conn.close()


def ensure_transfer_accounts():
    """确保转账主账号（alice01）与账户 A/B/C 就位、余额为初始值，并清掉名下多余账户。

    手工验证台的登录 / 转账场景在起 pytest 之前调用，避免"注册套件把 alice01
    删掉/改小"之后账户缺失，导致转账报"目标账户不存在"或下拉里选到 0 元账户。
    """
    _ensure_tables()
    user = PRESET_USERS[0]          # alice01：登录与转账的合规账号
    conn = get_db()
    c = conn.cursor()

    row = c.execute('SELECT id FROM pb_users WHERE username=?',
                    (user['username'],)).fetchone()
    if row:
        uid = row['id']
        c.execute('UPDATE pb_users SET password_hash=? WHERE id=?',
                  (generate_password_hash(user['password']), uid))
    else:
        c.execute('INSERT INTO pb_users (username, password_hash) VALUES (?, ?)',
                  (user['username'], generate_password_hash(user['password'])))
        uid = c.lastrowid

    keep = [acc for acc, _ in user['accounts']]
    marks = ','.join('?' * len(keep))
    c.execute(f'DELETE FROM pb_accounts WHERE user_id=? '
              f'AND account_number NOT IN ({marks})', [uid] + keep)
    for acc_no, balance in user['accounts']:
        exists = c.execute('SELECT id FROM pb_accounts WHERE account_number=?',
                           (acc_no,)).fetchone()
        if exists:
            c.execute('UPDATE pb_accounts SET user_id=?, balance=? '
                      'WHERE account_number=?', (uid, balance, acc_no))
        else:
            c.execute('INSERT INTO pb_accounts (user_id, account_number, balance) '
                      'VALUES (?, ?, ?)', (uid, acc_no, balance))

    conn.commit()
    conn.close()


def init_parabank_tables():
    """应用启动时调用：建表 + 预置演示数据。"""
    reset_demo_data()
    print('[pb] 预置演示数据就绪: ' +
          ', '.join(f"{u['username']}/{u['password']}" for u in PRESET_USERS))


def delete_user(username):
    """删除指定用户及其账户（注册套件执行前用来保证"用户名未注册"）。"""
    if not username:
        return
    conn = get_db()
    row = conn.execute('SELECT id FROM pb_users WHERE username=?',
                       (username,)).fetchone()
    if row:
        conn.execute('DELETE FROM pb_accounts WHERE user_id=?', (row['id'],))
        conn.execute('DELETE FROM pb_users WHERE id=?', (row['id'],))
        conn.commit()
    conn.close()


@pb_bp.route('/')
def index():
    if 'pb_user' not in session:
        return redirect(url_for('parabank.login'))
    return redirect(url_for('parabank.accounts'))


@pb_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        ok, msg = validate_login(username, password)
        if not ok:
            error = msg
        else:
            # 验证码在用户名/密码格式校验之后、账号密码比对之前校验：
            # 字段格式错误仍优先提示（与 LOGIN_004~015 的预期文案一致）
            ok, msg = validate_captcha(
                request.form.get('captcha'),
                session.get('pb_captcha'),
                session.get('pb_captcha_ts'),
                time.time())
            if not ok:
                error = msg
            else:
                conn = get_db()
                user = conn.execute("SELECT * FROM pb_users WHERE username=?",
                                    (username,)).fetchone()
                conn.close()
                # BUG-01：未区分"账号不存在"与"密码错误"（违反规则 2.1(5)(6)，
                #         预期 LOGIN_002、LOGIN_003 失败）
                if not user:
                    error = '用户名或密码错误' if INJECT_DEFECTS else '账号不存在'
                elif not check_password_hash(user['password_hash'], password):
                    error = '用户名或密码错误' if INJECT_DEFECTS else '密码错误'
                else:
                    session.pop('pb_captcha', None)
                    session.pop('pb_captcha_ts', None)
                    session['pb_user'] = username
                    session['pb_user_id'] = user['id']
                    return redirect(url_for('parabank.accounts'))

        # 任何一次提交后都换发新验证码：旧验证码不能重复使用
        new_captcha()
    else:
        # 打开/刷新登录页时换一张；有效期内的验证码继续沿用（刷新图片不会换码）
        if not session.get('pb_captcha') or captcha_expired():
            new_captcha()
    return render_template('parabank/login.html', error=error)


@pb_bp.route('/captcha/image')
def captcha_image():
    """验证码图片。?new=1 换一张（生成新码），否则沿用会话中的验证码。"""
    text = session.get('pb_captcha')
    if request.args.get('new') or not text or captcha_expired():
        text = new_captcha()
    resp = Response(_captcha_svg(text), mimetype='image/svg+xml')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@pb_bp.route('/captcha/text')
def captcha_text():
    """测试专用只读接口：返回当前会话的验证码文本（PB_CAPTCHA_TEST_HOOK=0 关闭）。"""
    if not CAPTCHA_TEST_HOOK:
        return jsonify({'error': 'captcha test hook disabled'}), 403
    text = session.get('pb_captcha')
    if not text:
        return jsonify({'error': 'no captcha in session'}), 404
    left = max(0, int(CAPTCHA_TTL - (time.time() - session.get('pb_captcha_ts', 0))))
    return jsonify({'text': text, 'expires_in': left})


@pb_bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''

        ok, msg = validate_register(username, password, confirm)
        if not ok:
            error = msg
        else:
            conn = get_db()
            exists = conn.execute("SELECT id FROM pb_users WHERE username=?",
                                  (username,)).fetchone()
            if exists:
                error = '用户名已存在'
                conn.close()
            else:
                conn.execute("INSERT INTO pb_users (username, password_hash) VALUES (?, ?)",
                             (username, generate_password_hash(password)))
                uid = conn.execute("SELECT id FROM pb_users WHERE username=?",
                                   (username,)).fetchone()['id']
                acc_num = str(20000 + uid)
                conn.execute("INSERT INTO pb_accounts (user_id, account_number, balance) VALUES (?, ?, ?)",
                             (uid, acc_num, 0.0))
                conn.commit()
                conn.close()
                success = '注册成功，请登录'
    return render_template('parabank/register.html', error=error, success=success)


@pb_bp.route('/accounts')
def accounts():
    if 'pb_user' not in session:
        return redirect(url_for('parabank.login'))
    conn = get_db()
    accs = conn.execute("SELECT * FROM pb_accounts WHERE user_id=? ORDER BY id",
                        (session['pb_user_id'],)).fetchall()
    conn.close()
    return render_template('parabank/accounts.html',
                           username=session['pb_user'],
                           accounts=[dict(a) for a in accs])


@pb_bp.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'pb_user' not in session:
        return redirect(url_for('parabank.login'))
    conn = get_db()
    error = None
    success = None

    if request.method == 'POST':
        from_acc = (request.form.get('from_account') or '').strip()
        to_acc = (request.form.get('to_account') or '').strip()
        amount_str = (request.form.get('amount') or '').strip()

        ok, amount, msg = validate_transfer(amount_str, from_acc, to_acc)
        if not ok:
            error = msg
        else:
            src = conn.execute("SELECT * FROM pb_accounts WHERE account_number=?",
                               (from_acc,)).fetchone()
            dst = conn.execute("SELECT * FROM pb_accounts WHERE account_number=?",
                               (to_acc,)).fetchone()
            if not src:
                error = '源账户不存在'
            elif not dst:
                error = '目标账户不存在'
            elif src['balance'] < amount:
                error = '账户余额不足'
            else:
                conn.execute("UPDATE pb_accounts SET balance=balance-? WHERE account_number=?",
                             (amount, from_acc))
                conn.execute("UPDATE pb_accounts SET balance=balance+? WHERE account_number=?",
                             (amount, to_acc))
                conn.execute("INSERT INTO pb_transactions (from_account, to_account, amount, txn_type, status) VALUES (?, ?, ?, 'TRANSFER', 'SUCCESS')",
                             (from_acc, to_acc, amount))
                conn.commit()
                success = ('转账成功: %s -> %s, 金额 %.2f 元'
                           % (from_acc, to_acc, amount))

    accs = conn.execute("SELECT * FROM pb_accounts WHERE user_id=? ORDER BY id",
                        (session['pb_user_id'],)).fetchall()
    conn.close()
    return render_template('parabank/transfer.html',
                           username=session['pb_user'],
                           accounts=[dict(a) for a in accs],
                           error=error, success=success)


@pb_bp.route('/transactions')
def transactions():
    if 'pb_user' not in session:
        return redirect(url_for('parabank.login'))
    conn = get_db()
    txs = conn.execute("SELECT * FROM pb_transactions ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return render_template('parabank/transactions.html',
                           username=session['pb_user'],
                           transactions=[dict(t) for t in txs])


@pb_bp.route('/logout')
def logout():
    session.pop('pb_user', None)
    session.pop('pb_user_id', None)
    return redirect(url_for('parabank.login'))
