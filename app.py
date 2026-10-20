import os
import re
import sys
import json
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime
from flask import send_from_directory, Flask, render_template, request, jsonify

from testcase_spec import CASES, MODULES, pytest_node

# 项目根目录 = 本文件所在目录（Windows / Linux 通用）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'parabank_test.db')
SUITES_DIR = os.path.join(BASE_DIR, 'pytest_suites')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)

# 套件与用例表由 testcase_spec.py 生成；用例表有变更时把版本号 +1，启动即自动重建
SEED_VERSION = 7

app = Flask(__name__, template_folder='templates', static_folder='static')
# 会话密钥：优先读环境变量；未设置时用本地演示缺省值
# （本仓库不包含任何第三方服务凭据）
app.secret_key = os.environ.get('PB_SECRET_KEY', 'parabank-lite-local-demo-key')


def get_db():
    # timeout：被测系统/多个套件同时读写时等待锁，避免 database is locked
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def finalize_stale_runs():
    """平台重启后，把上次遗留的 RUNNING 记录标记为 ERROR（其 pytest 已随平台终止）。"""
    conn = get_db()
    n = conn.execute(
        "UPDATE suite_runs SET status='ERROR', finished_at=CURRENT_TIMESTAMP "
        "WHERE status='RUNNING'").rowcount
    conn.commit()
    conn.close()
    if n:
        print(f'[platform] 已把 {n} 条遗留的 RUNNING 执行记录标记为 ERROR')


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS test_suites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        module TEXT,
        path TEXT,
        description TEXT,
        enabled INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS test_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        suite_id INTEGER,
        case_code TEXT,
        name TEXT NOT NULL,
        category TEXT,
        priority TEXT,
        steps TEXT,
        expected TEXT,
        pytest_node TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS suite_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        suite_id INTEGER,
        status TEXT,
        total INTEGER DEFAULT 0,
        passed INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        error INTEGER DEFAULT 0,
        skipped INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        triggered_by TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        case_id INTEGER,
        case_name TEXT,
        actual_result TEXT,
        status TEXT,
        duration_ms INTEGER,
        failure_reason TEXT,
        traceback TEXT,
        screenshot_path TEXT,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        display_name TEXT,
        role TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_res_run ON test_results(run_id);
    CREATE INDEX IF NOT EXISTS idx_res_status ON test_results(status);
    CREATE INDEX IF NOT EXISTS idx_runs_suite ON suite_runs(suite_id, started_at);
    ''')
    # 兼容旧库：补 test_results.actual_result（手工验证台的"系统实际提示"）
    cols = [r[1] for r in conn.execute('PRAGMA table_info(test_results)')]
    if 'actual_result' not in cols:
        conn.execute('ALTER TABLE test_results ADD COLUMN actual_result TEXT')
    conn.commit()
    conn.close()


def seed_data():
    """从 testcase_spec.py 生成套件与用例表；版本不一致时自动重建。"""
    conn = get_db()
    row = conn.execute("SELECT value FROM meta WHERE key='seed_version'").fetchone()
    if row and row['value'] == str(SEED_VERSION):
        conn.close()
        return

    c = conn.cursor()
    c.execute('DELETE FROM test_cases')
    c.execute('DELETE FROM test_suites')

    suite_id_of = {}
    for sid, m in enumerate(MODULES, start=1):
        c.execute('''INSERT INTO test_suites
                     (id, name, module, path, description, enabled)
                     VALUES (?, ?, ?, ?, ?, 1)''',
                  (sid, m['suite_name'], m['module'], m['path'], m['description']))
        suite_id_of[m['key']] = sid

    id_by_code = {}
    for case in CASES:
        cur = c.execute('''INSERT INTO test_cases
            (suite_id, case_code, name, category, priority, steps, expected, pytest_node)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (suite_id_of[case['suite']], case['code'], case['title'],
                   case['category'], case['priority'],
                   json.dumps(case['steps'], ensure_ascii=False),
                   case['expect'], pytest_node(case)))
        id_by_code[case['code']] = cur.lastrowid

    # 用例表重建后，按用例编号把历史结果重新对上
    # （test_results.case_name 形如 test_login[LOGIN_002]，据此回填 case_id）
    for code, cid in id_by_code.items():
        c.execute('''UPDATE test_results SET case_id=?
                     WHERE (case_id IS NULL
                            OR case_id NOT IN (SELECT id FROM test_cases))
                       AND case_name LIKE ?''', (cid, f'%[{code}]%'))

    c.execute('''INSERT OR IGNORE INTO users (username, display_name, role)
                 VALUES ('admin', '管理员', 'admin')''')
    c.execute('''INSERT INTO meta (key, value) VALUES ('seed_version', ?)
                 ON CONFLICT(key) DO UPDATE SET value=excluded.value''',
              (str(SEED_VERSION),))
    conn.commit()
    conn.close()
    print(f'[platform] 套件 {len(MODULES)} 个 / 用例 {len(CASES)} 条已按 testcase_spec 同步')


# ==================== API ====================

@app.route('/')
def index():
    return send_from_directory(os.path.join(BASE_DIR, 'static'), 'index.html')


@app.route('/api/stats')
def api_stats():
    conn = get_db()
    suites = conn.execute('SELECT COUNT(*) FROM test_suites').fetchone()[0]
    cases = conn.execute('SELECT COUNT(*) FROM test_cases').fetchone()[0]
    runs = conn.execute('SELECT COUNT(*) FROM suite_runs').fetchone()[0]

    # 手工验证（triggered_by='manual'）不进通过率统计：
    # 它记录的是"系统实际返回"，不是用例判定
    def _count(extra=''):
        return conn.execute(f'''
            SELECT COUNT(*) FROM test_results tr
            LEFT JOIN suite_runs r ON tr.run_id = r.id
            WHERE COALESCE(r.triggered_by, '') != 'manual' {extra}''').fetchone()[0]

    passed = _count("AND tr.status='PASS'")
    failed = _count("AND tr.status='FAIL'")
    error = _count("AND tr.status='ERROR'")
    total_res = _count()
    pass_rate = round(passed / total_res * 100, 1) if total_res > 0 else 0
    conn.close()
    return jsonify({
        'suites': suites, 'cases': cases, 'runs': runs,
        'passed': passed, 'failed': failed, 'error': error,
        'total_results': total_res, 'pass_rate': pass_rate
    })


@app.route('/api/suites')
def api_suites():
    conn = get_db()
    rows = conn.execute('SELECT * FROM test_suites ORDER BY id').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/cases')
def api_cases():
    suite_id = request.args.get('suite_id')
    conn = get_db()
    sql = '''SELECT tc.*, ts.name AS suite_name FROM test_cases tc
             LEFT JOIN test_suites ts ON tc.suite_id = ts.id'''
    params = []
    if suite_id:
        sql += ' WHERE tc.suite_id = ?'
        params.append(suite_id)
    sql += ' ORDER BY tc.id'
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/runs')
def api_runs():
    conn = get_db()
    rows = conn.execute('''
        SELECT r.*, s.name AS suite_name
        FROM suite_runs r
        LEFT JOIN test_suites s ON r.suite_id = s.id
        ORDER BY r.started_at DESC LIMIT 100
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/runs/<int:run_id>')
def api_run_detail(run_id):
    conn = get_db()
    run = conn.execute('SELECT * FROM suite_runs WHERE id=?', (run_id,)).fetchone()
    if not run:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    results = conn.execute('''
        SELECT * FROM test_results WHERE run_id=? ORDER BY id
    ''', (run_id,)).fetchall()
    conn.close()
    return jsonify({
        'run': dict(run),
        'results': [dict(r) for r in results]
    })


@app.route('/api/runs/<int:run_id>/progress')
def api_run_progress(run_id):
    """执行中的实时进度：直接读 pytest 日志（最终结果仍以跑完后的报告为准）。"""
    conn = get_db()
    run = conn.execute('SELECT * FROM suite_runs WHERE id=?', (run_id,)).fetchone()
    if not run:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    if run['triggered_by'] == 'manual':
        total = 1
    else:
        total = conn.execute('SELECT COUNT(*) FROM test_cases WHERE suite_id=?',
                             (run['suite_id'],)).fetchone()[0]
    conn.close()

    log_file = os.path.join(REPORTS_DIR, f'run_{run_id}.log')
    passed = failed = error = skipped = 0
    current = ''
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    m = re.search(r'::(\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED)', line)
                    if not m:
                        continue
                    current = m.group(1)
                    if m.group(2) == 'PASSED':
                        passed += 1
                    elif m.group(2) == 'FAILED':
                        failed += 1
                    elif m.group(2) == 'ERROR':
                        error += 1
                    else:
                        skipped += 1
        except Exception:
            pass

    return jsonify({
        'status': run['status'], 'done': passed + failed + error + skipped,
        'total': total, 'passed': passed, 'failed': failed, 'error': error,
        'skipped': skipped, 'current': current,
    })


@app.route('/api/results')
def api_results():
    """失败明细列表"""
    status = request.args.get('status')
    conn = get_db()
    sql = '''SELECT tr.*, s.name AS suite_name, r.started_at, r.triggered_by
             FROM test_results tr
             LEFT JOIN suite_runs r ON tr.run_id = r.id
             LEFT JOIN test_suites s ON r.suite_id = s.id'''
    params = []
    if status:
        sql += ' WHERE tr.status = ?'
        params.append(status)
    sql += ' ORDER BY tr.executed_at DESC LIMIT 200'
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/charts')
def api_charts():
    """饼图 + 折线图数据"""
    conn = get_db()

    # 饼图：按状态分布（不含手工验证执行）
    status_rows = conn.execute('''
        SELECT tr.status AS status, COUNT(*) c FROM test_results tr
        LEFT JOIN suite_runs r ON tr.run_id = r.id
        WHERE COALESCE(r.triggered_by, '') != 'manual'
        GROUP BY tr.status
    ''').fetchall()
    pie = [{'name': r['status'], 'value': r['c']} for r in status_rows]

    # 饼图2：按分类（不含手工验证执行）
    cat_rows = conn.execute('''
        SELECT tc.category, COUNT(*) c
        FROM test_results tr
        LEFT JOIN test_cases tc ON tr.case_id = tc.id
        LEFT JOIN suite_runs r ON tr.run_id = r.id
        WHERE COALESCE(r.triggered_by, '') != 'manual'
        GROUP BY tc.category
    ''').fetchall()
    pie_cat = [{'name': r['category'] or '未分类', 'value': r['c']} for r in cat_rows]

    # 折线图：近 7 天执行数量与通过/失败（数据源与统计、饼图一致：
    # 都取自 test_results，且不含手工验证执行）
    trend = conn.execute('''
        SELECT DATE(r.started_at) d,
               COUNT(DISTINCT r.id) runs,
               SUM(CASE WHEN tr.status = 'PASS' THEN 1 ELSE 0 END) passed,
               SUM(CASE WHEN tr.status IN ('FAIL', 'ERROR') THEN 1 ELSE 0 END) failed
        FROM test_results tr
        JOIN suite_runs r ON tr.run_id = r.id
        WHERE COALESCE(r.triggered_by, '') != 'manual'
        GROUP BY DATE(r.started_at)
        ORDER BY d DESC LIMIT 7
    ''').fetchall()
    trend = list(reversed([dict(r) for r in trend]))

    conn.close()
    return jsonify({'pie': pie, 'pie_cat': pie_cat, 'trend': trend})


# ==================== pytest 集成 ====================

def _classify_failure(longrepr):
    """把 pytest 的 longrepr 归类"""
    if not longrepr:
        return 'UNKNOWN_', ''
    text = str(longrepr)
    if 'AssertionError' in text:
        # 优先取 "E   AssertionError: xxx" 里的 xxx
        for line in text.split('\n'):
            s = line.strip()
            if s.startswith('E ') and 'AssertionError:' in s:
                detail = s.split('AssertionError:', 1)[1].strip()
                if detail:
                    return 'ASSERT_', detail[:200]
        # 取断言消息的第一行
        for line in text.split('\n'):
            s = line.strip()
            if (s.startswith('E ') and 'AssertionError' not in s
                    and not s[2:].strip().startswith('assert ')):
                return 'ASSERT_', s[2:].strip()[:200]
        return 'ASSERT_', '断言失败'
    if 'Failed:' in text:
        # pytest.fail() 抛的是 Failed，同样按断言失败归类，取冒号后的消息
        for line in text.split('\n'):
            s = line.strip()
            if s.startswith('E ') and 'Failed:' in s:
                detail = s.split('Failed:', 1)[1].strip()
                if detail:
                    return 'ASSERT_', detail[:200]
    if 'TimeoutException' in text or 'Timed out' in text:
        return 'TIMEOUT_', '元素等待超时'
    if 'NoSuchElement' in text:
        return 'NOELEMENT_', '元素未找到'
    if 'WebDriverException' in text or 'ConnectionError' in text:
        return 'DRIVER_', '浏览器驱动异常'
    if 'requests' in text.lower() or 'HTTP' in text:
        return 'NETWORK_', '网络请求失败'
    # 兜底：取最后一行
    lines = [l for l in text.split('\n') if l.strip()]
    return 'UNKNOWN_', lines[-1][:200] if lines else '未知错误'


# 手工验证台的场景 → pytest 测试函数
MANUAL_SUITE = 'manual_suite'
SCENARIOS = {
    'login': 'test_manual.py::test_manual_login',
    'register': 'test_manual.py::test_manual_register',
    'transfer': 'test_manual.py::test_manual_transfer',
}

# 手工验证台留空字段的预置值（与页面占位符一致）
MANUAL_DEFAULTS = {
    'login': {'username': 'alice01', 'password': 'Pass123'},
    'register': {'password': 'Pass123'},
    'transfer': {'from_account': '10001', 'to_account': '10002', 'amount': '100'},
}


def _run_suite_async(run_id, suite_id, suite_path, params=None, case_code=None,
                     scenario=None):
    """后台线程里执行 pytest。

    case_code 非空 —— 只跑该条用例（单条执行）
    scenario  非空 —— 手工验证台：跑一次真实操作，把"系统实际返回"写进 actual_result
    """
    report_file = os.path.join(REPORTS_DIR, f'run_{run_id}.json')
    log_file = os.path.join(REPORTS_DIR, f'run_{run_id}.log')
    observed_file = os.path.join(REPORTS_DIR, f'run_{run_id}_observed.json')
    suite_abs = os.path.join(SUITES_DIR, suite_path)

    # 定位要跑的 pytest 节点
    mod = next((m for m in MODULES if m['path'] == suite_path), None)
    case = next((c for c in CASES if c['code'] == case_code), None) if case_code else None
    if scenario:
        target = f"{suite_abs}{os.sep}{SCENARIOS[scenario]}"
    elif mod and case:
        target = (f"{suite_abs}{os.sep}{mod['test_file']}::"
                  f"{mod['test_func']}[{case['code']}]")
    else:
        target = suite_abs

    started = time.time()
    env = os.environ.copy()
    # Windows 下确保 pytest 子进程按 UTF-8 读写
    env.setdefault('PYTHONUTF8', '1')
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    if scenario:
        env['PB_SCENARIO'] = scenario
        env['PB_RESULT_FILE'] = observed_file
    overrides = {k: str(v).strip() for k, v in (params or {}).items() if str(v).strip()}
    for k, v in overrides.items():
        env[f'PB_{k.upper()}'] = v

    timeout_sec = 120 + 40 * (1 if (case or scenario) else _suite_case_count(suite_path))
    run_error = ''
    try:
        # pytest 输出落到 reports/run_<id>.log，出问题时可直接查看
        with open(log_file, 'w', encoding='utf-8') as log:
            subprocess.run(
                [sys.executable, '-m', 'pytest', target,
                 '--json-report',
                 f'--json-report-file={report_file}',
                 '-v', '--tb=short', '--no-header'],
                stdout=log, stderr=subprocess.STDOUT,
                timeout=timeout_sec, env=env,
                encoding='utf-8', errors='replace'
            )
    except subprocess.TimeoutExpired:
        run_error = f'pytest 执行超时（超过 {timeout_sec}s），已中止'
        print(f'[platform] run {run_id}: {run_error}')
    except Exception as e:
        run_error = f'pytest 启动失败：{e}'
        print(f'[platform] run {run_id}: {run_error}')

    duration = int((time.time() - started) * 1000)

    # 手工验证台：读测试写下的"系统实际返回"
    observed = {}
    if os.path.exists(observed_file):
        try:
            with open(observed_file, 'r', encoding='utf-8') as f:
                observed = json.load(f)
        except Exception:
            observed = {}

    # 解析报告
    passed = failed = error = skipped = total = 0
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            summary = report.get('summary', {})
            passed = summary.get('passed', 0)
            failed = summary.get('failed', 0)
            error = summary.get('error', 0)
            skipped = summary.get('skipped', 0)
            total = summary.get('total', passed + failed + error + skipped)

            conn = get_db()
            for t in report.get('tests', []):
                nodeid = t.get('nodeid', '')
                case_name = nodeid.split('::')[-1]
                outcome = t.get('outcome', 'unknown')  # passed / failed / error / skipped
                dur = int(t.get('duration', 0) * 1000)

                status_map = {'passed': 'PASS', 'failed': 'FAIL',
                              'error': 'ERROR', 'skipped': 'SKIP'}
                st = status_map.get(outcome, 'UNKNOWN')

                failure_reason = ''
                tb_text = ''
                if st in ('FAIL', 'ERROR'):
                    call = t.get('call') or t.get('setup') or {}
                    longrepr = call.get('longrepr', '')
                    prefix, msg = _classify_failure(longrepr)
                    failure_reason = f'{prefix}{msg}'[:500]
                    tb_text = str(longrepr)[:4000]

                # 尝试匹配 case_id
                row = conn.execute(
                    'SELECT id FROM test_cases WHERE pytest_node LIKE ?',
                    (f'%{case_name}%',)
                ).fetchone()
                case_id = row['id'] if row else None

                conn.execute('''
                    INSERT INTO test_results
                    (run_id, case_id, case_name, status, duration_ms, failure_reason,
                     traceback, actual_result)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (run_id, case_id, case_name, st, dur, failure_reason, tb_text,
                      observed.get('message', '')))
            conn.commit()
            conn.close()
        except Exception as e:
            run_error = run_error or f'解析报告失败：{e}'
            print(f'[platform] run {run_id}: {run_error}')

    # 无论成败都要收尾，避免执行记录永远停在 RUNNING
    try:
        conn = get_db()
        if total == 0:
            overall = 'ERROR'
        else:
            overall = 'PASS' if failed == 0 and error == 0 else 'FAIL'
        conn.execute('''
            UPDATE suite_runs SET status=?, total=?, passed=?, failed=?, error=?,
                                  skipped=?, duration_ms=?, finished_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (overall, total, passed, failed, error, skipped, duration, run_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[platform] run {run_id} 收尾失败：{e}')

    if run_error:
        try:
            conn = get_db()
            conn.execute('''
                INSERT INTO test_results
                (run_id, case_id, case_name, status, duration_ms, failure_reason)
                VALUES (?, NULL, ?, 'ERROR', ?, ?)
            ''', (run_id, f'[套件执行异常] {suite_path}', duration, run_error[:500]))
            conn.commit()
            conn.close()
        except Exception:
            pass


def _suite_case_count(suite_path):
    mod = next((m for m in MODULES if m['path'] == suite_path), None)
    return len([c for c in CASES if mod and c['suite'] == mod['key']]) or 1


@app.route('/api/manual/run', methods=['POST'])
def api_manual_run():
    """手工验证：按你填的参数跑一次真实操作，结果记录"系统实际返回"。"""
    data = request.get_json(silent=True) or {}
    scenario = str(data.get('scenario') or '').strip()
    if scenario not in SCENARIOS:
        return jsonify({'error': f'未知场景：{scenario}'}), 400

    params = {k: str(v).strip() for k, v in (data.get('params') or {}).items()
              if str(v).strip()}
    # 手工验证前先把转账主账号与 A/B/C 账户就位（注册套件可能把 alice01 删掉/改小）
    if scenario in ('login', 'transfer'):
        ensure_transfer_accounts()

    # 留空 = 用预置值（与页面占位符一致）
    for key, value in MANUAL_DEFAULTS[scenario].items():
        params.setdefault(key, value)
    if scenario == 'register':
        # 用户名留空 = 帮你造一个新用户（"假装新用户"）
        params.setdefault('username', f'alice{int(time.time())}')
        params.setdefault('confirm', params['password'])

    conn = get_db()
    run_id = conn.execute('''
        INSERT INTO suite_runs (suite_id, status, triggered_by, started_at)
        VALUES (NULL, 'RUNNING', 'manual', CURRENT_TIMESTAMP)
    ''').lastrowid
    conn.commit()
    conn.close()

    t = threading.Thread(target=_run_suite_async,
                         args=(run_id, None, MANUAL_SUITE, params, None, scenario))
    t.daemon = True
    t.start()

    return jsonify({'ok': True, 'run_id': run_id, 'params': params})


@app.route('/api/suites/<int:suite_id>/run', methods=['POST'])
def api_run_suite(suite_id):
    # case_code 非空 = 只跑这一条（手工单条执行）；
    # params 里填了的字段才生效（留空 = 用文档固定测试数据）
    data = request.get_json(silent=True) or {}
    params = {k: v for k, v in (data.get('params') or {}).items() if str(v).strip()}
    case_code = str(data.get('case_code') or '').strip()

    conn = get_db()
    suite = conn.execute('SELECT * FROM test_suites WHERE id=?', (suite_id,)).fetchone()
    if not suite:
        conn.close()
        return jsonify({'error': 'suite not found'}), 404

    mod = next((m for m in MODULES if m['path'] == suite['path']), None)
    if case_code and not any(c['code'] == case_code
                             for c in CASES if mod and c['suite'] == mod['key']):
        conn.close()
        return jsonify({'error': f'用例 {case_code} 不属于该套件'}), 400

    # 检查是否已有 RUNNING
    running = conn.execute(
        "SELECT id FROM suite_runs WHERE suite_id=? AND status='RUNNING'",
        (suite_id,)
    ).fetchone()
    if running:
        conn.close()
        return jsonify({'error': '该套件正在执行中'}), 409

    triggered_by = 'manual' if case_code else ('web+params' if params else 'web')
    cur = conn.execute('''
        INSERT INTO suite_runs (suite_id, status, triggered_by, started_at)
        VALUES (?, 'RUNNING', ?, CURRENT_TIMESTAMP)
    ''', (suite_id, triggered_by))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    t = threading.Thread(target=_run_suite_async,
                         args=(run_id, suite_id, suite['path'], params, case_code))
    t.daemon = True
    t.start()

    return jsonify({'ok': True, 'run_id': run_id, 'case_code': case_code or None})


from parabank_lite import (ensure_transfer_accounts, init_parabank_tables,
                           pb_bp)
init_parabank_tables()
app.register_blueprint(pb_bp, url_prefix='/parabank')

if __name__ == '__main__':
    init_db()
    seed_data()
    finalize_stale_runs()
    app.run(host='0.0.0.0', port=5000, debug=False)