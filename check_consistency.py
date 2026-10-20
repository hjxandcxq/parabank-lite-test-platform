# -*- coding: utf-8 -*-
"""前后一致性校验：文档 ↔ testcase_spec ↔ 被测系统 ↔ 平台库 ↔ pytest 套件。

用法：
    python check_consistency.py            # 全量校验（含 pytest 收集、平台库）
    python check_consistency.py --no-pytest --no-db   # 只校验文档与用例表/被测系统

每一步都会打印 ✓ / ✗，末尾给出汇总，存在 ✗ 时退出码为 1。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import testcase_spec as spec  # noqa: E402

# 期望结果由数据层（数据库查询）决定、校验层应放行的用例
DATA_LAYER_CASES = {
    'LOGIN_002': '密码比对（check_password_hash）',
    'LOGIN_003': '账号存在性查询',
    'REG_010': '用户名唯一性查询',
    'TRAN_016': '源账户余额校验',
    'TRAN_019': '目标账户存在性查询',
}

# 本期用例表基线（用例表调整后在这里同步一次，用来兜住误改）
EXPECT_CASES = {'login': 19, 'register': 22, 'transfer': 19}
EXPECT_PRIORITY = {'P0': 19, 'P1': 40, 'P2': 1}

RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(f"{'✓' if ok else '✗'} {name}" + (f" —— {detail}" if detail else ''))
    return ok


def validate_case(case):
    """按用例数据回放被测系统的校验层，返回 (是否通过, 提示文案)。"""
    import parabank_lite as pb

    f = case['form']
    if case['suite'] == 'login':
        ok, msg = pb.validate_login(f['username'], f['password'])
        if ok:
            # 登录页已加图形验证码：格式校验通过后按用例的 captcha_mode 回放
            ok, msg = pb.validate_captcha(spec.captcha_input(case),
                                          spec.CAPTCHA_SAMPLE)
        return ok, msg
    if case['suite'] == 'register':
        return pb.validate_register(f['username'], f['password'], f['confirm'])
    ok, _amount, msg = pb.validate_transfer(f['amount'], f['from_account'],
                                            f['to_account'])
    return ok, msg


# ============ A. 用例表自洽 ============
def check_spec():
    codes = [c['code'] for c in spec.CASES]
    total_cases = sum(EXPECT_CASES.values())
    check(f'用例表：共 {total_cases} 条且编号唯一',
          len(codes) == total_cases and len(set(codes)) == total_cases,
          f'实际 {len(codes)} 条')

    rows, total = spec.summary()
    per_suite = {m['key']: len(spec.cases_of(m['key'])) for m in spec.MODULES}
    check('用例表：模块分组 ' + ' / '.join(f'{k} {v}' for k, v in EXPECT_CASES.items()),
          per_suite == EXPECT_CASES, str(per_suite))
    check('用例表：优先级合计 ' + ' '.join(f'{k}={v}' for k, v in EXPECT_PRIORITY.items()),
          (total['P0'], total['P1'], total['P2']) ==
          (EXPECT_PRIORITY['P0'], EXPECT_PRIORITY['P1'], EXPECT_PRIORITY['P2']),
          f"实际 P0={total['P0']} P1={total['P1']} P2={total['P2']}")

    bad = [c['code'] for c in spec.CASES
           if (c['expect_msg'] is None) != c['success']]
    check('用例表：成功用例与期望提示互斥', not bad, ','.join(bad))

    bad = [c['code'] for c in spec.CASES
           if c['priority'] not in ('P0', 'P1', 'P2')
           or c['category'] not in ('功能', '异常')
           or not c['steps'] or not c['expect']]
    check('用例表：优先级/分类/步骤/预期结果齐全', not bad, ','.join(bad))


# ============ B. 被测系统与用例表 / 缺陷清单的偏差一致 ============
def _conforms_to_spec(case):
    """校验层是否符合用例表，返回 (符合?, 说明)。"""
    ok, msg = validate_case(case)
    if case['code'] in DATA_LAYER_CASES:
        return ok, f'校验层提前拦截：{msg}'
    if case['success']:
        return ok, f'期望成功，实际提示：{msg}'
    if ok:
        return False, f'期望提示「{case["expect_msg"]}」，实际校验通过'
    return msg == case['expect_msg'], f'期望「{case["expect_msg"]}」，实际「{msg}」'


def check_sut():
    import parabank_lite as pb

    src = Path(pb.__file__).read_text(encoding='utf-8')
    validator_defects = [d for d in spec.INJECTED_DEFECTS if d['layer'] == 'validator']

    missing_marks = [d['id'] for d in spec.INJECTED_DEFECTS if d['id'] not in src]
    check('被测系统：缺陷标记齐全（BUG-xx，可定位可开关）', not missing_marks,
          ','.join(missing_marks))

    missing_msg, deviation, not_reproduced = [], [], []
    for case in spec.CASES:
        defect = spec.defect_of(case['code'])
        if case['code'] in DATA_LAYER_CASES and case['expect_msg'] not in src:
            missing_msg.append(f"{case['code']} 数据层提示缺失：{case['expect_msg']}")
        conform, detail = _conforms_to_spec(case)
        if defect is None:
            if not conform:
                deviation.append(f"{case['code']} 未登记偏差：{detail}")
        elif defect['layer'] == 'validator' and conform:
            not_reproduced.append(f"{case['code']}（{defect['id']}）校验层未复现：{detail}")

    check('被测系统：数据层提示文案存在', not missing_msg, ' | '.join(missing_msg))
    check('被测系统：未登记偏差为 0（除缺陷清单外与用例表一致）', not deviation,
          ' | '.join(deviation[:4]))
    check(f'被测系统：{len(validator_defects)} 处校验层缺陷已复现',
          not not_reproduced, ' | '.join(not_reproduced[:4]))
    check('被测系统：预置演示数据与用例表一致',
          spec.PRESET_USERS == pb.PRESET_USERS,
          f'spec={spec.PRESET_USERS} / pb={pb.PRESET_USERS}')


# ============ C. 平台库（test_suites / test_cases）一致 ============
def check_db():
    import app as platform

    platform.init_db()
    platform.seed_data()

    conn = platform.get_db()
    suites = [dict(r) for r in conn.execute('SELECT * FROM test_suites ORDER BY id')]
    cases = [dict(r) for r in conn.execute('SELECT * FROM test_cases ORDER BY id')]
    conn.close()

    check('平台库：套件 3 个且名称/模块/路径与用例表一致',
          [(s['name'], s['module'], s['path']) for s in suites] ==
          [(m['suite_name'], m['module'], m['path']) for m in spec.MODULES],
          str([(s['name'], s['module'], s['path']) for s in suites]))

    db_by_code = {c['case_code']: c for c in cases}
    want_codes = [c['code'] for c in spec.CASES]
    expect_total = sum(EXPECT_CASES.values())
    check(f'平台库：用例 {expect_total} 条且编号一致',
          len(cases) == expect_total and set(db_by_code) == set(want_codes),
          f'实际 {len(cases)} 条')

    diff = []
    for case in spec.CASES:
        row = db_by_code.get(case['code'])
        if not row:
            continue
        expect = {
            'name': case['title'], 'category': case['category'],
            'priority': case['priority'], 'expected': case['expect'],
            'pytest_node': spec.pytest_node(case),
        }
        for key, val in expect.items():
            if row[key] != val:
                diff.append(f"{case['code']}.{key}: 库[{row[key]}] ≠ 用例表[{val}]")
    check('平台库：用例名称/分类/优先级/预期/节点 与用例表一致', not diff,
          ' | '.join(diff[:5]))

    check('平台库：用例套件归属正确',
          all(db_by_code[c['code']]['suite_id'] ==
              next(i for i, m in enumerate(spec.MODULES, start=1) if m['key'] == c['suite'])
              for c in spec.CASES))


# ============ D. pytest 套件覆盖一致 ============
# 用 pytest 插件回调精确取节点名（-q 的树状输出各版本格式不统一）
COLLECT_SCRIPT = r'''
import json
import sys

import pytest


class _Collector:
    def pytest_collection_finish(self, session):
        print('NODEIDS=' + json.dumps([item.nodeid for item in session.items]))


sys.exit(pytest.main([sys.argv[1], '--collect-only', '-q', '-p', 'no:cacheprovider'],
                     plugins=[_Collector()]))
'''


def collect_nodeids(suite_dir):
    import json

    proc = subprocess.run(
        [sys.executable, '-c', COLLECT_SCRIPT, str(suite_dir)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=str(suite_dir))
    for line in proc.stdout.splitlines():
        if line.startswith('NODEIDS='):
            return json.loads(line[len('NODEIDS='):])
    raise RuntimeError(f'pytest 收集失败：{(proc.stdout + proc.stderr)[-400:]}')


def check_pytest():
    for m in spec.MODULES:
        suite_dir = ROOT / 'pytest_suites' / m['path']
        want = [spec.pytest_node(c) for c in spec.cases_of(m['key'])]
        try:
            nodeids = collect_nodeids(suite_dir)
        except Exception as e:
            check(f"pytest 套件：{m['path']} 收集用例", False, str(e))
            continue
        check(f"pytest 套件：{m['path']} 收集到 {len(want)} 条且节点名一致",
              sorted(nodeids) == sorted(want),
              f'实际 {len(nodeids)} 条；差异 {sorted(set(want) ^ set(nodeids))[:3]}')


# ============ E. 文档一致 ============
def check_docs():
    import gen_case_doc

    ok, detail = gen_case_doc.check()
    check('文档：docs/测试用例设计.md 与用例表同步', ok, detail)

    rules_md = (ROOT / 'docs' / '测试规则文档.md').read_text(encoding='utf-8')
    check('文档：测试规则文档.md 使用 LOGIN_001 风格编号',
          not re.search(r'TC-[A-Z]+-\d+', rules_md) and 'LOGIN_001' in rules_md)
    expect_total = sum(EXPECT_CASES.values())
    ok_count = f'共 {expect_total} 条' in rules_md
    check(f'文档：测试规则文档.md 已写明 {expect_total} 条用例', ok_count,
          '' if ok_count else f"未找到「共 {expect_total} 条」")


# ============ F. 被测系统在线（可选） ============
def check_online():
    import requests

    from browser_setup import BASE_URL
    try:
        r = requests.get(f'{BASE_URL}/login', timeout=10)
        check('被测系统在线：/parabank/login 返回 200',
              r.status_code == 200 and 'username' in r.text,
              f'HTTP {r.status_code} · {BASE_URL}')
    except Exception as e:
        check('被测系统在线：/parabank/login 返回 200', False,
              f'{type(e).__name__}: 请先启动 python app.py（{BASE_URL}）')


# ============ E. 平台执行结果与缺陷清单一致 ============
def check_runs():
    """按套件比对：最近一次标准执行的失败集合，必须等于缺陷清单里属于该套件的部分。

    只跑过部分套件也算通过（未执行的套件只提示），避免"还没跑完就报警"。
    """
    import app as platform

    expected = set(spec.expected_failures())
    tested, problems, pending = [], [], []

    conn = platform.get_db()
    for sid, m in enumerate(spec.MODULES, start=1):
        # 只认标准执行（triggered_by='web'）；手工验证/带参数执行不入统计
        run = conn.execute(
            "SELECT id FROM suite_runs WHERE suite_id=? AND status != 'RUNNING' "
            "AND triggered_by = 'web' ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
        if not run:
            pending.append(m['module'])
            continue

        tested.append(m['module'])
        failed = set()
        for row in conn.execute(
                '''SELECT tc.case_code, tr.status FROM test_results tr
                   LEFT JOIN test_cases tc ON tr.case_id = tc.id
                   WHERE tr.run_id = ?''', (run['id'],)):
            if row['status'] in ('FAIL', 'ERROR') and row['case_code']:
                failed.add(row['case_code'])
        want = {c['code'] for c in spec.cases_of(m['key']) if c['code'] in expected}
        if failed != want:
            problems.append(f"{m['module']}：多失败 {sorted(failed - want)}，"
                            f"漏失败 {sorted(want - failed)}")
    conn.close()

    if not tested:
        check('平台执行结果：失败集合 == 缺陷清单（尚无标准执行，跳过）', True,
              '到"测试套件"页点"执行整套件"')
        return

    detail = ' | '.join(problems)
    if pending:
        detail += f"（尚未标准执行：{'、'.join(pending)}）"
    import parabank_lite as pb
    if not pb.INJECT_DEFECTS:
        detail += '；缺陷总开关 INJECT_DEFECTS 已关闭'
    check(f'平台执行结果：已标准执行的 {len(tested)} 个套件，失败集合 == 缺陷清单',
          not problems, detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-pytest', action='store_true', help='跳过 pytest 收集校验')
    ap.add_argument('--no-db', action='store_true', help='跳过平台库与执行结果校验')
    ap.add_argument('--online', action='store_true', help='额外校验被测系统可访问')
    args = ap.parse_args()

    print('=' * 66)
    print('  ParaBank Lite 前后一致性校验')
    print('=' * 66)
    print('--- A. 用例表（testcase_spec.py）---')
    check_spec()
    print('--- B. 被测系统（parabank_lite.py）---')
    check_sut()
    if not args.no_db:
        print('--- C. 测试平台库（parabank_test.db）---')
        check_db()
    if not args.no_pytest:
        print('--- D. pytest 套件 ---')
        check_pytest()
    if not args.no_db:
        print('--- E. 平台执行结果（失败集合 vs 缺陷清单）---')
        check_runs()
    print('--- F. 文档 ---')
    check_docs()
    if args.online:
        print('--- G. 被测系统在线 ---')
        check_online()

    failed = [r for r in RESULTS if not r['ok']]
    print('=' * 66)
    print(f"  校验项 {len(RESULTS)} 个，通过 {len(RESULTS) - len(failed)} 个，失败 {len(failed)} 个")
    for r in failed:
        print(f"  ✗ {r['name']} —— {r['detail']}")
    print('=' * 66)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
