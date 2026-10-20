# -*- coding: utf-8 -*-
"""从 testcase_spec.py 生成 docs/测试用例设计.md，保证文档与用例表同步。

用法：
    python gen_case_doc.py          # 重新生成文档
    python gen_case_doc.py --check  # 只校验文档是否与用例表同步（不同步则退出码 1）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import testcase_spec as spec  # noqa: E402
from check_consistency import DATA_LAYER_CASES, validate_case  # noqa: E402

DOC = ROOT / 'docs' / '测试用例设计.md'


def _rules_of(module):
    return [r for r in spec.RULES if r['module'] == module]


def _outcome(case):
    """被测系统实际返回的提示文案（校验层实跑；数据层/路由层缺陷另行标注）。"""
    if case['code'] in DATA_LAYER_CASES:
        return f"数据层：{DATA_LAYER_CASES[case['code']]}"
    defect = spec.defect_of(case['code'])
    if defect and defect['layer'] == 'route':
        return f"{defect['id']}：{defect['title']}"
    ok, msg = validate_case(case)
    if not ok:
        return msg
    if case['success']:
        return {'login': '校验通过 → 跳转账户概览',
                'register': '校验通过 → 注册成功',
                'transfer': '校验通过 → 转账成功'}[case['suite']]
    return '校验通过（用例表预期提示未出现）'


def build():
    L = []
    add = L.append
    counts = {m['key']: len(spec.cases_of(m['key'])) for m in spec.MODULES}
    total_cases = len(spec.CASES)

    add('# ParaBank Lite 业务规则与测试用例设计')
    add('')
    add('> 本文件由 `gen_case_doc.py` 依据 `testcase_spec.py` 生成，请勿手工编辑；'
        '改用例请改用例表后重新生成。')
    add('> 原始需求：《ParaBank Lite 业务规则与测试用例设计.docx》')
    add('')

    # ---------- 一、系统定义 ----------
    add('## 一、系统定义')
    add('')
    add('| 项目 | 内容 |')
    add('|------|------|')
    add('| 系统名称 | ParaBank Lite（自建简易银行系统） |')
    add('| 被测地址 | http://localhost:5000/parabank/ |')
    add('| 测试平台 | http://localhost:5000/ |')
    for u in spec.PRESET_USERS:
        add(f"| 预置账号 | {u['username']} / {u['password']}，账户 "
            + '、'.join(f"{a}（{b:.2f}）" for a, b in u['accounts']) + ' |')
    add('| 核心模块 | 登录、注册、转账（账户查询本期无规则与用例，未纳入套件） |')
    add(f"| 用例总数 | {total_cases} 条（登录 {counts['login']} + "
        f"注册 {counts['register']} + 转账 {counts['transfer']}） |")
    add(f"| 系统状态 | 已注入 {len(spec.INJECTED_DEFECTS)} 处缺陷（演示用，见第七节），"
        f"预期 {len(spec.expected_failures())} 条用例失败；"
        f"关闭 parabank_lite.INJECT_DEFECTS 即恢复 {total_cases} 条全绿 |")
    add('')

    # ---------- 二、业务规则 ----------
    add('## 二、业务规则')
    add('')
    for i, m in enumerate(spec.MODULES, start=1):
        add(f'### 2.{i} {m["module"]}模块规则')
        add('')
        for r in _rules_of(m['module']):
            add(f"{r['no']}. {r['text']}")
        add('')
    add('### 转账账户定义（文档二节末原文）')
    add('')
    add(spec.BASE_DATA)
    add('')
    add('### 落地口径（相对文档的偏差）')
    add('')
    add('| 模块 | 规则 | 落地口径 |')
    add('|------|------|----------|')
    for r in spec.RULES:
        if r['deviation']:
            add(f"| {r['module']} | {r['text']} | {r['deviation']} |")
    add('')

    # ---------- 三、等价类划分 ----------
    add('## 三、等价类划分')
    add('')
    for i, m in enumerate(spec.MODULES, start=1):
        add(f'### 3.{i} {m["module"]}模块')
        add('')
        add('| 参数 | 说明 | 有效 | 有效数据 | 无效 | 无效数据 |')
        add('|------|------|------|----------|------|----------|')
        for row in spec.EQUIVALENCE[m['module']]:
            add('| ' + ' | '.join(row) + ' |')
        add('')

    # ---------- 四、测试用例表 ----------
    add('## 四、测试用例表')
    add('')
    add('分类口径：有效等价类用例记为「功能」，无效等价类用例记为「异常」。')
    add('')
    for i, m in enumerate(spec.MODULES, start=1):
        add(f'### 4.{i} {m["module"]}模块')
        add('')
        add('| 用例编号 | 用例标题 | 项目/模块 | 优先级 | 分类 | 前置条件 | 测试步骤 | 测试数据 | 预期结果 | pytest 节点 |')
        add('|----------|----------|-----------|--------|------|----------|----------|----------|----------|-------------|')
        for c in spec.cases_of(m['key']):
            add('| ' + ' | '.join([
                c['code'], c['title'], c['module'], c['priority'], c['category'],
                c['precondition'],
                '<br>'.join(c['steps']), c['data'], c['expect'],
                spec.pytest_node(c),
            ]) + ' |')
        add('')

    # ---------- 五、汇总统计 ----------
    rows, total = spec.summary()
    add('## 五、汇总统计')
    add('')
    add('| 模块 | 规则数 | 等价类数 | 用例数 | P0 | P1 | P2 |')
    add('|------|--------|----------|--------|----|----|----|')
    for r in rows + [total]:
        add(f"| {r['module']} | {r['rules']} | {r['equivalent']} | {r['cases']} "
            f"| {r['P0']} | {r['P1']} | {r['P2']} |")
    add('')
    add('说明：本表按用例表实际统计。原文档第五节给出的优先级分布'
        '（登录 3/4/3、注册 3/11/3、转账 5/9/4，合计 11/24/10）与用例表行不一致，'
        '此处以用例表为准。')
    add('')
    fail_by_module = {}
    for code in spec.expected_failures():
        case = next(c for c in spec.CASES if c['code'] == code)
        name = spec.module_of(case['suite'])['module']
        fail_by_module[name] = fail_by_module.get(name, 0) + 1
    add(f"其中 {len(spec.expected_failures())} 条为预期失败（注入缺陷所致："
        + '、'.join(f'{k} {v} 条' for k, v in fail_by_module.items())
        + "）；登录验证码 4 条（LOGIN_016~019）为本次扩展，其余用例取自原文档用例表。")
    add('')

    # ---------- 六、提示文案对照 ----------
    add('## 六、提示文案对照（用例表 ↔ 被测系统）')
    add('')
    add('| 用例编号 | 期望提示 | 层级 | 被测系统实际文案 | 缺陷 |')
    add('|----------|----------|------|------------------|------|')
    for c in spec.CASES:
        layer = '数据层' if c['code'] in DATA_LAYER_CASES else ('校验层' if not c['success'] else '成功')
        defect = spec.defect_of(c['code'])
        add(f"| {c['code']} | {c['expect_msg'] or '（预期成功）'} | {layer} "
            f"| {_outcome(c)} | {defect['id'] if defect else ''} |")
    add('')
    add('标注了缺陷编号的行即被测系统偏离文档之处，对应的 pytest 用例会真实失败'
        '（缺陷归属见第七节）。')
    add('')
    add('断言口径：pytest 用例对提示文案做**全等匹配**（非包含匹配），'
        '「期望提示」列即被测系统返回的完整文案；同一条规则在登录表与注册表里'
        '写法不同的（密码字符集文案），按各模块表分别实现。')
    add('')

    # ---------- 七、注入缺陷清单 ----------
    add('## 七、注入缺陷清单（演示用）')
    add('')
    add(f'用例表照原文档第四节，共 {total_cases} 条（登录验证码 4 条为本次扩展）；'
        '下列缺陷全部注入在被测系统一侧，用于演示测试平台的失败归因能力。'
        '每个缺陷在 `parabank_lite.py` 中都有 `BUG-xx` 标记，'
        '总开关 `INJECT_DEFECTS = False` 即恢复为完全符合文档的系统。')
    add('')
    add('| 缺陷编号 | 缺陷标题 | 违反的文档规则 | 预期失败用例 | 预期归因 | 缺陷说明 |')
    add('|----------|----------|----------------|--------------|----------|----------|')
    for d in spec.INJECTED_DEFECTS:
        add(f"| {d['id']} | {d['title']} | {d['rule']} | {'、'.join(d['cases'])} "
            f"| {d['expect_prefix']} | {d['desc']} |")
    add('')
    add(f"合计 {len(spec.INJECTED_DEFECTS)} 处缺陷 → "
        f"{len(spec.expected_failures())} 条用例预期失败（"
        + '、'.join(f'{k} {v} 条' for k, v in fail_by_module.items()) + "）。")
    add('')

    # ---------- 八、待确认事项的落地决定 ----------
    add('## 八、文档第六节待确认事项的落地决定')
    add('')
    add('| # | 事项 | 决定 |')
    add('|---|------|------|')
    for i, d in enumerate(spec.DECISIONS, start=1):
        add(f"| {i} | {d['item']} | {d['decision']} |")
    add('')

    # ---------- 九、一致性校验 ----------
    add('## 九、一致性校验')
    add('')
    add('```bash')
    add('python check_consistency.py --online   # 用例表 / 被测系统 / 平台库 / pytest / 执行结果 / 文档')
    add('python gen_case_doc.py                # 用例表变更后重新生成本文档')
    add('```')
    add('')
    add('被测系统、平台库、pytest 套件、本文件均由 `testcase_spec.py` 派生，'
        '任何一处改动都会被校验脚本发现。其中"平台执行结果"一项会比对'
        f"三个套件最近一次执行的实际失败集合与缺陷清单（{len(spec.expected_failures())} 条），"
        '多失败或少失败都会报错。')
    add('')
    return '\n'.join(L)


def check():
    """返回 (是否同步, 说明)。"""
    want = build()
    if not DOC.exists():
        return False, 'docs/测试用例设计.md 不存在，请运行 python gen_case_doc.py'
    have = DOC.read_text(encoding='utf-8')
    if have == want:
        return True, f'{len(spec.CASES)} 条用例表与文档一致'
    return False, 'docs/测试用例设计.md 已过期，请运行 python gen_case_doc.py 重新生成'


def main():
    want = build()
    if '--check' in sys.argv:
        ok, detail = check()
        print(('✓ ' if ok else '✗ ') + detail)
        return 0 if ok else 1
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(want, encoding='utf-8')
    print(f'✓ 已生成 {DOC}（{len(spec.CASES)} 条用例）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
