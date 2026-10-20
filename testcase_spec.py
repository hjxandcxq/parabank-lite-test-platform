# -*- coding: utf-8 -*-
"""ParaBank Lite 业务规则与测试用例设计 —— 单一事实来源（spec）。

来源：《ParaBank Lite 业务规则与测试用例设计（最新版）.docx》
     《等价类划分与测试用例.xlsx》（六个工作表：三模块的等价类 + 用例表）

被测系统（parabank_lite.py）、pytest 套件（pytest_suites/*）、
测试平台 seed（app.py）与文档（docs/测试用例设计.md）全部由本文件派生，
改这里即可全局同步，一致性由 check_consistency.py 校验。

用例字段说明：
    code         用例编号，如 LOGIN_001 / REG_001 / TRAN_001
    title        用例标题
    module       项目/模块，如 登录页
    suite        所属套件 key：login / register / transfer
    priority     P0 / P1 / P2
    category     功能 / 异常（有效等价类→功能，无效等价类→异常）
    precondition 前置条件
    steps        测试步骤（list）
    data         测试数据（展示用文案，与用例表一致）
    form         提交给被测系统的实际字段值
    expect       预期结果（展示用文案，与用例表一致）
    expect_msg   期望提示文案，None 表示预期成功
    success      True 表示该用例预期成功
"""

# ============================================================
# 一、套件定义（与测试平台 test_suites 一一对应）
# ============================================================
MODULES = [
    {
        'key': 'login', 'suite_name': '登录模块测试', 'module': '登录',
        'path': 'login_suite', 'case_prefix': 'LOGIN',
        'description': '验证 ParaBank Lite 登录流程（19 条用例，含图形验证码）',
        'test_file': 'test_login.py', 'test_func': 'test_login',
        'base_path': '/login',
    },
    {
        'key': 'register', 'suite_name': '注册模块测试', 'module': '注册',
        'path': 'register_suite', 'case_prefix': 'REG',
        'description': '验证 ParaBank Lite 注册流程（22 条用例）',
        'test_file': 'test_register.py', 'test_func': 'test_register',
        'base_path': '/register',
    },
    {
        'key': 'transfer', 'suite_name': '转账模块测试', 'module': '转账',
        'path': 'transfer_suite', 'case_prefix': 'TRAN',
        'description': '验证 ParaBank Lite 转账流程（19 条用例）',
        'test_file': 'test_transfer.py', 'test_func': 'test_transfer',
        'base_path': '/transfer',
    },
]

# ============================================================
# 二、业务规则（文档第二节原文 + 落地口径）
# ============================================================
RULES = [
    # ---- 登录 ----
    {'module': '登录', 'no': 1, 'text': '用户名必填，长度 6 ~ 20 位', 'deviation': ''},
    {'module': '登录', 'no': 2, 'text': '用户名只允许字母、数字、下划线', 'deviation': ''},
    {'module': '登录', 'no': 3, 'text': '密码必填，长度 6 ~ 20 位', 'deviation': ''},
    {'module': '登录', 'no': 4, 'text': '密码只允许字母、数字和字符 @ # $ . _', 'deviation': ''},
    {'module': '登录', 'no': 5, 'text': '用户名必须已在系统中注册', 'deviation': ''},
    {'module': '登录', 'no': 6, 'text': '密码必须与注册时一致', 'deviation': ''},
    {'module': '登录', 'no': 7, 'text': '用户名或密码任一为空时，不允许提交', 'deviation': ''},
    {'module': '登录', 'no': 8,
     'text': '验证码必填，4 位字母数字，不区分大小写，有效期 120 秒且一次性使用',
     'deviation': '原文档未包含的扩展规则：本次为登录页新增图形验证码。校验顺序为'
                  '用户名/密码格式 → 验证码 → 账号密码比对，失败一次即换发新验证码'},
    # ---- 注册 ----
    {'module': '注册', 'no': 1, 'text': '用户名必填，长度 6 ~ 20 位', 'deviation': ''},
    {'module': '注册', 'no': 2, 'text': '用户名只允许字母、数字、下划线', 'deviation': ''},
    {'module': '注册', 'no': 3, 'text': '用户名必须全局唯一，不能与已有账号重复', 'deviation': ''},
    {'module': '注册', 'no': 4, 'text': '密码必填，长度 6 ~ 20 位', 'deviation': ''},
    {'module': '注册', 'no': 5, 'text': '密码必须同时包含字母和数字，且只允许字母、数字和字符 @ # $ . _',
     'deviation': ''},
    {'module': '注册', 'no': 6, 'text': '确认密码必须与密码保持一致', 'deviation': ''},
    # ---- 转账 ----
    {'module': '转账', 'no': 1, 'text': '转账金额必填', 'deviation': ''},
    {'module': '转账', 'no': 2, 'text': '金额范围 0.01 ~ 50000.00 元', 'deviation': ''},
    {'module': '转账', 'no': 3, 'text': '金额最多保留 2 位小数', 'deviation': ''},
    {'module': '转账', 'no': 4, 'text': '金额只能包含数字和一个小数点',
     'deviation': 'TRAN_007（-50）要求提示"金额必须大于0"，故校验顺序为：字符集 → 小数点个数 '
                  '→ 格式 → 小数位 → 数值范围；负号放行到数值校验'},
    {'module': '转账', 'no': 5, 'text': '源账户余额必须 ≥ 转账金额',
     'deviation': '账户 C（10003）初始余额 100.00，供 TRAN_016（余额不足）与 '
                  'TRAN_017（余额等于转账金额）使用'},
    {'module': '转账', 'no': 6, 'text': '源账户和目标账户不能相同', 'deviation': ''},
    {'module': '转账', 'no': 7, 'text': '目标账户必须存在', 'deviation': ''},
]

# 文档二节末的转账账户定义（原文，落地按此实现）
BASE_DATA = (
    '转账测试中用字母 A、B、C、D 表示账户：账户 A 为正常源账户（初始余额 100000.00 元）；'
    '账户 B 为正常目标账户（初始余额 0.00 元）；账户 C 为余额不足专用账户（初始余额 100.00 元）；'
    '账户 D 表示不存在的目标账户。每次执行用例前测试数据恢复至上述初始状态。'
    '所有转账用例统一使用已注册账号 alice01 / Pass123 登录。'
)

# 落地口径（文档本身需要澄清的地方）
DECISIONS = [
    {'item': '转账账户 A/B/C/D',
     'decision': 'A=账户 10001、B=账户 10002、C=账户 10003、D=99999（不存在），'
                 '均属于预置测试主账号 alice01；套件（及手工验证台）执行前复位余额'},
    {'item': '登录/转账的合规账号',
     'decision': '统一用预置账号 alice01 / Pass123（文档等价类与用例表指定），'
                 '该账号同时持有 A/B/C 三个账户'},
    {'item': '初始账号 admin / admin123',
     'decision': '按文档「系统定义」保留为预置账号（不持有账户）'},
    {'item': '含中文的用户名（LOGIN_009 / REG_008）',
     'decision': '文档给"用户01"只有 4 位、会先命中长度校验，落地补足位数'
                 '（用户0001）以命中字符集校验'},
    {'item': '注册成功用例复用同一用户名',
     'decision': 'REG_013 / REG_014 / REG_018 都用 user_01 且预期注册成功，'
                 '因此注册套件每条用例前会删除该用例要注册的用户名，'
                 '保证"用户名未注册"这一隐含前置条件成立'},
    {'item': '转账成功用例的余额断言',
     'decision': 'TRAN_001 预期结果写明"A余额减少100、B余额增加100"，'
                 'TRAN_017 写明"验证余额≥转账金额"；套件对成功用例额外校验'
                 '源账户减少额与目标账户增加额均等于转账金额'},
    {'item': '文档 docx 与 xlsx 的等价类示例数据不一致',
     'decision': 'docx 3.1/3.2 的示例仍写 admin_01、user_2026，xlsx 已改为 alice01 等；'
                 '以 xlsx（与用例表一致）为准落地'},
    {'item': '两模块密码字符集文案差异',
     'decision': '登录表"密码只允许字母、数字和字符@#$._"、注册表"密码只能包含字母、数字和@#$._"，'
                 '按各模块表分别实现（用户名字符集文案两表已统一为"包含…"）'},
    {'item': '核心模块"账户查询" / 交易流水查询',
     'decision': '本期不做：文档未给规则与用例，系统与平台也不展示流水'},
    {'item': '是否需要"用户被锁定"规则', 'decision': '暂不加'},
    {'item': '登录是否区分"账号不存在"与"密码错误"',
     'decision': '区分（LOGIN_002/003 分开，提示文案分别实现）'},
    {'item': '登录图形验证码（扩展）',
     'decision': '原文档未包含。本次为登录页新增 4 位图形验证码（SVG，不区分大小写、'
                 '120 秒有效、一次提交即作废），并补 LOGIN_016~019 四条用例；'
                 '自动化通过测试专用只读接口 GET /parabank/captcha/text 取码，'
                 '设 PB_CAPTCHA_TEST_HOOK=0 可关闭该接口（关闭后自动化登录会失败）'},
]

# ============================================================
# 三、等价类划分
# ============================================================
EQUIVALENCE = {
    '登录': [
        ('用户名', '长度', '6~20 位', 'alice01、abcdef、abcdefghijklmnopqrst', '＜6 位或＞20 位',
         'alice、21 位用户名'),
        ('用户名', '字符类型', '字母、数字、下划线', 'alice01、user_01', '含特殊字符、中文、空格',
         'alice@1、用户01、alice 01'),
        ('用户名', '空值', '非空', 'alice01', '为空', '（空）'),
        ('用户名', '存在性', '已注册', 'alice01', '未注册', 'bob_01'),
        ('密码', '长度', '6~20 位', 'Pass123、Pass12、20 位合法密码', '＜6 位或＞20 位',
         'Pass1、21 位密码'),
        ('密码', '字符类型', '字母、数字、@#$._', 'Pass123、Pass@123',
         '含其他特殊字符、中文、空格', 'Pass%123、Pass中123、Pass 123'),
        ('密码', '空值', '非空', 'Pass123', '为空', '（空）'),
        ('密码', '一致性', '与注册时密码一致', 'Pass123', '与注册时密码不一致', 'Pass124'),
        ('验证码', '内容', '非空、与图形一致、不区分大小写', 'AB3D、ab3d',
         '为空、不一致、已使用', '（空）、0000、上一次用过的验证码'),
        ('验证码', '时效', '120 秒内且一次性使用', '页面新生成的验证码', '超时或重复使用',
         '过期验证码、刷新前的旧验证码'),
    ],
    '注册': [
        ('用户名', '长度', '6~20 位', 'alice01、abcdef、abcdefghijklmnopqrst', '＜6 位或＞20 位',
         'alice、21 位用户名'),
        ('用户名', '字符类型', '字母、数字、下划线', 'alice01、user_01', '含特殊字符、中文、空格',
         'alice@1、用户01、alice 01'),
        ('用户名', '空值', '非空', 'alice01', '为空', '（空）'),
        ('用户名', '唯一性', '未注册', '（新用户名）user_01', '已注册', 'alice01'),
        ('密码', '长度', '6~20 位', 'Pass123、Pass12、20 位合法密码', '＜6 位或＞20 位',
         'Pass1、21 位密码'),
        ('密码', '组成', '同时包含字母和数字', 'Pass123、abc123', '纯字母或纯数字', 'abcdef、123456'),
        ('密码', '字符类型', '字母、数字、@#$._', 'Pass123、Pass@123、Pass_123',
         '含其他特殊字符、中文、空格', 'Pass%123、Pass中123、Pass 123'),
        ('密码', '空值', '非空', 'Pass123', '为空', '（空）'),
        ('确认密码', '一致性', '与密码完全一致', '密码：Pass123；确认密码：Pass123', '与密码不一致',
         '密码：Pass123；确认密码：Pass124'),
    ],
    '转账': [
        ('转账金额', '范围', '0.01~50000.00', '100、0.01、50000.00', '≤0 或 >50000',
         '0、-50、50000.01'),
        ('转账金额', '小数位', '最多 2 位', '100、100.5、100.50', '超过 2 位', '100.123、100.999'),
        ('转账金额', '字符类型', '仅数字和小数点', '100.5', '含其他字符', '100a、一百、1,000'),
        ('转账金额', '小数点个数', '最多 1 个', '100、100.50', '超过 1 个', '1.2.3、1..2'),
        ('转账金额', '空值', '非空', '100', '为空', '（空）'),
        ('转账金额', '格式校验', '合法数字格式', '0.01、100.50', '非法数字格式', '.、.123'),
        ('源账户', '账户存在性', '账户存在', 'A、C', '账户不存在', 'D'),
        ('余额', '余额充足性', '余额 ≥ 转账金额', 'A 余额 100000 转账 100；C 余额 100 转账 100',
         '余额 < 转账金额', 'C 余额 100 转账 200'),
        ('源账户/目标账户', '账户关系', '源账户与目标账户不同', 'A→B', '源账户与目标账户相同', 'A→A'),
        ('目标账户', '账户存在性', '目标账户存在', 'B', '目标账户不存在', 'D'),
    ],
}

# ============================================================
# 四、预置演示数据（被测系统初始化，套件执行前会重置）
# ============================================================
# alice01：测试主账号 —— 登录与转账用例的合规账号，持有 A/B/C 三个账户
# admin：文档「系统定义」里的初始账号，不持有账户
PRESET_USERS = [
    {'username': 'alice01', 'password': 'Pass123',
     'accounts': [('10001', 100000.00), ('10002', 0.00), ('10003', 100.00)]},
    {'username': 'admin', 'password': 'admin123', 'accounts': []},
]

# 转账账户 A / B / C / D（见文档二节末的账户定义）
ACC_A = '10001'           # 正常源账户，初始余额 100000.00
ACC_B = '10002'           # 正常目标账户，初始余额 0.00
ACC_C = '10003'           # 余额不足专用账户，初始余额 100.00
ACC_D = '99999'           # 不存在的目标账户

# 登录/转账用例统一使用的账号（文档指定）
MAIN_USER = ('alice01', 'Pass123')
TRANSFER_USER = MAIN_USER

_LOGIN_DEFAULTS = {'username': 'alice01', 'password': 'Pass123'}
_REG_DEFAULTS = {'password': 'Pass123', 'confirm': 'Pass123'}
_LONG_NAME = 'a' * 21
_LONG_PWD = 'Pass12345678901234567'      # 21 位：合规字符，超长

# 登录验证码（扩展）：captcha_mode 决定自动化怎么填验证码，
# 一致性校验用下面的样例值回放校验层（运行时验证码是随机生成的）。
CAPTCHA_SAMPLE = 'AB3D'
CAPTCHA_INPUTS = {
    'valid': CAPTCHA_SAMPLE,             # 正确
    'lower': CAPTCHA_SAMPLE.lower(),     # 正确（小写）
    'blank': '',                         # 为空
    'wrong': '0000',                     # 错误（字符集不含 0）
    'reuse': 'QW7X',                     # 已使用/刷新前的旧码
}


def captcha_input(case):
    """用例提交的验证码文本（供一致性校验回放）。"""
    return CAPTCHA_INPUTS.get(case.get('captcha_mode', 'valid'), CAPTCHA_SAMPLE)


def _login(code, title, priority, category, username, password,
           expect_msg, expect, data,
           steps=('1. 输入用户名', '2. 输入密码', '3. 输入正确验证码', '4. 点击登录'),
           precondition='打开登录页', captcha_mode='valid'):
    return {
        'code': code, 'title': title, 'module': '登录页', 'suite': 'login',
        'priority': priority, 'category': category,
        'precondition': precondition, 'steps': list(steps), 'data': data,
        'form': {'username': username, 'password': password},
        'expect': expect, 'expect_msg': expect_msg,
        'success': expect_msg is None,
        'captcha_mode': captcha_mode,
        'pytest_node_suffix': f'[{code}]',
    }


def _reg(code, title, priority, category, username=None, password=None,
         confirm=None, expect_msg=None, expect='', data='',
         steps=('1. 输入用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册'),
         precondition='打开注册页', precondition_user_exists=False):
    form = {
        'username': username if username is not None else 'alice01',
        'password': password if password is not None else _REG_DEFAULTS['password'],
        'confirm': confirm if confirm is not None else (
            password if password is not None else _REG_DEFAULTS['confirm']),
    }
    return {
        'code': code, 'title': title, 'module': '注册页', 'suite': 'register',
        'priority': priority, 'category': category,
        'precondition': precondition, 'steps': list(steps), 'data': data,
        'form': form, 'expect': expect, 'expect_msg': expect_msg,
        'success': expect_msg is None,
        'precondition_user_exists': precondition_user_exists,
        'pytest_node_suffix': f'[{code}]',
    }


def _tran(code, title, priority, category, amount, expect_msg,
          expect='', data='', from_acc=ACC_A, to_acc=ACC_B,
          steps=('1. 输入转账金额', '2. 选择目标账户', '3. 提交')):
    return {
        'code': code, 'title': title, 'module': '转账页', 'suite': 'transfer',
        'priority': priority, 'category': category,
        'precondition': '使用 alice01/Pass123 登录，测试数据已复位',
        'steps': list(steps), 'data': data,
        'form': {'from_account': from_acc, 'to_account': to_acc, 'amount': amount},
        'expect': expect, 'expect_msg': expect_msg,
        'success': expect_msg is None,
        'pytest_node_suffix': f'[{code}]',
    }


# ============================================================
# 五、测试用例表（60 条：登录 19 + 注册 22 + 转账 19）
# ============================================================
CASES = [
    # ---------------- 登录模块（15 条） ----------------
    _login('LOGIN_001', '合法登录', 'P0', '功能', 'alice01', 'Pass123', None,
           '合法，登录成功', '用户名：alice01；密码：Pass123',
           precondition='系统已存在账号 alice01，密码为 Pass123'),
    _login('LOGIN_002', '密码错误', 'P0', '异常', 'alice01', 'Pass124', '密码错误',
           '不合法，提示"密码错误"，不允许登录', '用户名：alice01；密码：Pass124',
           steps=('1. 输入已注册用户名', '2. 输入错误密码', '3. 输入正确验证码', '4. 点击登录'),
           precondition='系统已存在账号 alice01'),
    _login('LOGIN_003', '账号不存在', 'P0', '异常', 'bob_01', 'Pass123', '账号不存在',
           '不合法，提示"账号不存在"，不允许登录', '用户名：bob_01；密码：Pass123',
           steps=('1. 输入未注册用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_004', '用户名为空', 'P1', '异常', '', 'Pass123', '用户名必填',
           '不合法，提示"用户名必填"，不允许提交', '用户名：（空）；密码：Pass123',
           steps=('1. 用户名留空', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_005', '密码为空', 'P1', '异常', 'alice01', '', '密码必填',
           '不合法，提示"密码必填"，不允许提交', '用户名：alice01；密码：（空）',
           steps=('1. 输入合法用户名', '2. 密码留空', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_006', '用户名过短', 'P1', '异常', 'alice', 'Pass123', '用户名长度6-20位',
           '不合法，提示"用户名长度6-20位"', '用户名：alice；密码：Pass123',
           steps=('1. 输入 5 位用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_007', '用户名过长', 'P1', '异常', 'abcdefghijklmnopqrstu', 'Pass123',
           '用户名长度6-20位', '不合法，提示"用户名长度6-20位"',
           '用户名：abcdefghijklmnopqrstu；密码：Pass123',
           steps=('1. 输入 21 位用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_008', '用户名含特殊字符', 'P1', '异常', 'alice@1', 'Pass123',
           '用户名只能包含字母、数字和下划线',
           '不合法，提示"用户名只能包含字母、数字和下划线"',
           '用户名：alice@1；密码：Pass123',
           steps=('1. 输入含特殊字符的用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_009', '用户名含中文', 'P1', '异常', '用户0001', 'Pass123',
           '用户名只能包含字母、数字和下划线',
           '不合法，提示"用户名只能包含字母、数字和下划线"',
           '用户名：用户01；密码：Pass123',
           steps=('1. 输入含中文的用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_010', '用户名含空格', 'P1', '异常', 'alice 01', 'Pass123',
           '用户名只能包含字母、数字和下划线',
           '不合法，提示"用户名只能包含字母、数字和下划线"',
           '用户名：alice 01；密码：Pass123',
           steps=('1. 输入含空格的用户名', '2. 输入合法密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_011', '密码过短', 'P1', '异常', 'alice01', 'Pass1', '密码长度6-20位',
           '不合法，提示"密码长度6-20位"', '用户名：alice01；密码：Pass1',
           steps=('1. 输入合法用户名', '2. 输入 5 位密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_012', '密码过长', 'P1', '异常', 'alice01', 'abcdefghijklmnop12345',
           '密码长度6-20位', '不合法，提示"密码长度6-20位"',
           '用户名：alice01；密码：abcdefghijklmnop12345',
           steps=('1. 输入合法用户名', '2. 输入 21 位密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_013', '密码含非法特殊字符', 'P1', '异常', 'alice01', 'Pass%123',
           '密码只允许字母、数字和字符@#$._',
           '不合法，提示"密码只允许字母、数字和字符@#$._"',
           '用户名：alice01；密码：Pass%123',
           steps=('1. 输入合法用户名', '2. 输入含非法特殊字符的密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_014', '密码含中文', 'P1', '异常', 'alice01', 'Pass中123',
           '密码只允许字母、数字和字符@#$._',
           '不合法，提示"密码只允许字母、数字和字符@#$._"',
           '用户名：alice01；密码：Pass中123',
           steps=('1. 输入合法用户名', '2. 输入含中文的密码', '3. 输入正确验证码', '4. 点击登录')),
    _login('LOGIN_015', '密码含空格', 'P1', '异常', 'alice01', 'Pass 123',
           '密码只允许字母、数字和字符@#$._',
           '不合法，提示"密码只允许字母、数字和字符@#$._"',
           '用户名：alice01；密码：Pass 123',
           steps=('1. 输入合法用户名', '2. 输入含空格的密码', '3. 输入正确验证码', '4. 点击登录')),

    # ---- 登录验证码（扩展，4 条） ----
    _login('LOGIN_016', '验证码为空', 'P1', '异常', 'alice01', 'Pass123',
           '验证码必填', '不合法，提示"验证码必填"，不允许登录',
           '用户名：alice01；密码：Pass123；验证码：（空）',
           steps=('1. 输入合法用户名和密码', '2. 验证码留空', '3. 点击登录'),
           precondition='打开登录页，验证码已生成', captcha_mode='blank'),
    _login('LOGIN_017', '验证码错误', 'P0', '异常', 'alice01', 'Pass123',
           '验证码错误', '不合法，提示"验证码错误"，不允许登录',
           '用户名：alice01；密码：Pass123；验证码：0000',
           steps=('1. 输入合法用户名和密码', '2. 输入与图形不符的验证码', '3. 点击登录'),
           precondition='打开登录页，验证码已生成', captcha_mode='wrong'),
    _login('LOGIN_018', '验证码不区分大小写', 'P1', '功能', 'alice01', 'Pass123',
           None, '合法，验证码按小写输入仍登录成功',
           '用户名：alice01；密码：Pass123；验证码：图形验证码的小写形式',
           steps=('1. 输入合法用户名和密码', '2. 把验证码转为小写输入', '3. 点击登录'),
           precondition='打开登录页，验证码已生成', captcha_mode='lower'),
    _login('LOGIN_019', '验证码一次性使用', 'P1', '异常', 'alice01', 'Pass123',
           '验证码错误', '不合法，已使用的验证码再次提交提示"验证码错误"',
           '用户名：alice01；密码：Pass123；验证码：上一次提交用过的验证码',
           steps=('1. 用正确验证码提交一次（密码错误）', '2. 页面换发新验证码',
                  '3. 仍填入旧验证码并提交', '4. 系统拒绝登录'),
           precondition='打开登录页，已知当前验证码', captcha_mode='reuse'),

    # ---------------- 注册模块（22 条） ----------------
    _reg('REG_001', '合法注册', 'P0', '功能', username='alice01',
         data='用户名：alice01；密码：Pass123；确认密码：Pass123',
         expect='合法，注册成功',
         precondition='打开注册页，alice01 尚未注册'),
    _reg('REG_002', '用户名为空', 'P1', '异常', username='', expect_msg='用户名必填',
         data='用户名：（空）；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示"用户名必填"',
         steps=('1. 用户名留空', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_003', '用户名过短', 'P1', '异常', username='alice', expect_msg='用户名长度6-20位',
         data='用户名：alice；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示"用户名长度6-20位"',
         steps=('1. 输入 5 位用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_004', '用户名最小边界', 'P0', '功能', username='abc123',
         data='用户名：abc123；密码：Pass123；确认密码：Pass123',
         expect='合法，注册成功',
         steps=('1. 输入 6 位用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_005', '用户名最大边界', 'P0', '功能', username='abcdefghijklmnopqrst',
         data='用户名：abcdefghijklmnopqrst；密码：Pass123；确认密码：Pass123',
         expect='合法，注册成功',
         steps=('1. 输入 20 位用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_006', '用户名超长', 'P1', '异常', username='abcdefghijklmnopqrstu',
         expect_msg='用户名长度6-20位',
         data='用户名：abcdefghijklmnopqrstu；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示"用户名长度6-20位"',
         steps=('1. 输入 21 位用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_007', '用户名含特殊字符', 'P1', '异常', username='alice@1',
         expect_msg='用户名只能包含字母、数字和下划线',
         data='用户名：alice@1；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示"用户名只能包含字母、数字和下划线"',
         steps=('1. 输入含特殊字符的用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_008', '用户名含中文', 'P1', '异常', username='用户0001',
         expect_msg='用户名只能包含字母、数字和下划线',
         data='用户名：用户01；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示用户名格式错误',
         steps=('1. 输入含中文的用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_009', '用户名含空格', 'P1', '异常', username='alice 01',
         expect_msg='用户名只能包含字母、数字和下划线',
         data='用户名：alice 01；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示用户名格式错误',
         steps=('1. 输入含空格的用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册')),
    _reg('REG_010', '用户名已存在', 'P0', '异常', username='alice01',
         expect_msg='用户名已存在',
         data='用户名：alice01；密码：Pass123；确认密码：Pass123',
         expect='不合法，提示"用户名已存在"',
         steps=('1. 输入已有用户名', '2. 输入密码', '3. 输入确认密码', '4. 点击注册'),
         precondition='系统中已存在 alice01 账号', precondition_user_exists=True),
    _reg('REG_011', '密码为空', 'P1', '异常', username='user_01', password='', confirm='',
         expect_msg='密码必填',
         data='用户名：user_01；密码：（空）；确认密码：（空）',
         expect='不合法，提示"密码必填"',
         steps=('1. 输入合法用户名', '2. 密码留空', '3. 确认密码留空', '4. 点击注册')),
    _reg('REG_012', '密码过短', 'P1', '异常', username='user_01', password='Pass1',
         expect_msg='密码长度6-20位',
         data='用户名：user_01；密码：Pass1；确认密码：Pass1',
         expect='不合法，提示"密码长度6-20位"',
         steps=('1. 输入合法用户名', '2. 输入 5 位密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_013', '密码最小边界', 'P0', '功能', username='user_01', password='Pass12',
         data='用户名：user_01；密码：Pass12；确认密码：Pass12',
         expect='合法，注册成功',
         steps=('1. 输入合法用户名', '2. 输入 6 位密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_014', '密码最大边界', 'P0', '功能', username='user_01',
         password='abcdefghijklmnop1234',
         data='用户名：user_01；密码：abcdefghijklmnop1234；确认密码：abcdefghijklmnop1234',
         expect='合法，注册成功',
         steps=('1. 输入合法用户名', '2. 输入 20 位密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_015', '密码超长', 'P1', '异常', username='user_01',
         password='abcdefghijklmnop12345', expect_msg='密码长度6-20位',
         data='用户名：user_01；密码：abcdefghijklmnop12345；确认密码：abcdefghijklmnop12345',
         expect='不合法，提示"密码长度6-20位"',
         steps=('1. 输入合法用户名', '2. 输入 21 位密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_016', '密码纯字母', 'P1', '异常', username='user_01', password='abcdef',
         expect_msg='密码必须包含字母和数字',
         data='用户名：user_01；密码：abcdef；确认密码：abcdef',
         expect='不合法，提示"密码必须包含字母和数字"',
         steps=('1. 输入合法用户名', '2. 输入纯字母密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_017', '密码纯数字', 'P1', '异常', username='user_01', password='123456',
         expect_msg='密码必须包含字母和数字',
         data='用户名：user_01；密码：123456；确认密码：123456',
         expect='不合法，提示"密码必须包含字母和数字"',
         steps=('1. 输入合法用户名', '2. 输入纯数字密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_018', '密码含合法特殊字符', 'P0', '功能', username='user_01',
         password='Pass@123',
         data='用户名：user_01；密码：Pass@123；确认密码：Pass@123',
         expect='合法，注册成功',
         steps=('1. 输入合法用户名', '2. 输入含允许特殊字符的密码',
                '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_019', '密码含非法特殊字符', 'P1', '异常', username='user_01',
         password='Pass%123', expect_msg='密码只能包含字母、数字和@#$._',
         data='用户名：user_01；密码：Pass%123；确认密码：Pass%123',
         expect='不合法，提示"密码只能包含字母、数字和@#$._"',
         steps=('1. 输入合法用户名', '2. 输入含非法特殊字符的密码',
                '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_020', '密码含中文', 'P1', '异常', username='user_01', password='Pass中123',
         expect_msg='密码只能包含字母、数字和@#$._',
         data='用户名：user_01；密码：Pass中123；确认密码：Pass中123',
         expect='不合法，提示密码格式错误',
         steps=('1. 输入合法用户名', '2. 输入含中文的密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_021', '密码含空格', 'P1', '异常', username='user_01', password='Pass 123',
         expect_msg='密码只能包含字母、数字和@#$._',
         data='用户名：user_01；密码：Pass 123；确认密码：Pass 123',
         expect='不合法，提示密码格式错误',
         steps=('1. 输入合法用户名', '2. 输入含空格的密码', '3. 输入相同确认密码', '4. 点击注册')),
    _reg('REG_022', '两次密码不一致', 'P0', '异常', username='user_01', password='Pass123',
         confirm='Pass124', expect_msg='两次密码不一致',
         data='用户名：user_01；密码：Pass123；确认密码：Pass124',
         expect='不合法，提示"两次密码不一致"',
         steps=('1. 输入合法用户名', '2. 输入密码', '3. 输入不同的确认密码', '4. 点击注册')),

    # ---------------- 转账模块（19 条） ----------------
    _tran('TRAN_001', '合法整数金额', 'P0', '功能', '100', None,
          '合法，转账成功，A余额减少100，B余额增加100',
          '源账户：A；目标账户：B；金额：100'),
    _tran('TRAN_002', '合法 1 位小数', 'P0', '功能', '100.5', None,
          '合法，转账成功', '源账户：A；目标账户：B；金额：100.5'),
    _tran('TRAN_003', '合法 2 位小数', 'P0', '功能', '100.50', None,
          '合法，转账成功', '源账户：A；目标账户：B；金额：100.50'),
    _tran('TRAN_004', '最小金额边界', 'P0', '功能', '0.01', None,
          '合法，转账成功', '源账户：A；目标账户：B；金额：0.01'),
    _tran('TRAN_005', '最大金额边界', 'P0', '功能', '50000.00', None,
          '合法，转账成功', '源账户：A；目标账户：B；金额：50000.00'),
    _tran('TRAN_006', '金额为 0', 'P1', '异常', '0', '金额必须大于0',
          '不合法，提示金额必须大于0', '源账户：A；目标账户：B；金额：0'),
    _tran('TRAN_007', '金额为负数', 'P1', '异常', '-50', '金额必须大于0',
          '不合法，提示金额必须大于0', '源账户：A；目标账户：B；金额：-50'),
    _tran('TRAN_008', '金额超过上限', 'P1', '异常', '50000.01', '单笔金额不能超过50000元',
          '不合法，提示单笔金额不能超过50000元', '源账户：A；目标账户：B；金额：50000.01'),
    _tran('TRAN_009', '金额超过 2 位小数', 'P1', '异常', '100.999', '金额最多保留2位小数',
          '不合法，提示金额最多保留2位小数', '源账户：A；目标账户：B；金额：100.999'),
    _tran('TRAN_010', '金额含字母', 'P1', '异常', '100a', '只能输入数字和小数点',
          '不合法，提示只能输入数字和小数点', '源账户：A；目标账户：B；金额：100a'),
    _tran('TRAN_011', '金额含中文', 'P1', '异常', '一百', '只能输入数字和小数点',
          '不合法，提示只能输入数字和小数点', '源账户：A；目标账户：B；金额：一百'),
    _tran('TRAN_012', '金额含逗号', 'P1', '异常', '1,000', '只能输入数字和小数点',
          '不合法，提示只能输入数字和小数点', '源账户：A；目标账户：B；金额：1,000'),
    _tran('TRAN_013', '多个小数点', 'P1', '异常', '1.2.3', '仅允许一个小数点',
          '不合法，提示仅允许一个小数点', '源账户：A；目标账户：B；金额：1.2.3'),
    _tran('TRAN_014', '仅输入小数点', 'P2', '异常', '.', '请输入有效金额',
          '不合法，提示请输入有效金额', '源账户：A；目标账户：B；金额：.'),
    _tran('TRAN_015', '金额为空', 'P1', '异常', '', '转账金额不能为空',
          '不合法，提示转账金额不能为空', '源账户：A；目标账户：B；金额：（空）',
          steps=('1. 金额留空', '2. 选择目标账户', '3. 提交')),
    _tran('TRAN_016', '余额不足', 'P0', '异常', '200', '账户余额不足',
          '不合法，提示账户余额不足', '源账户：C；目标账户：B；金额：200', from_acc=ACC_C),
    _tran('TRAN_017', '余额等于转账金额', 'P0', '功能', '100', None,
          '合法，转账成功，验证余额≥转账金额', '源账户：C；目标账户：B；金额：100',
          from_acc=ACC_C),
    _tran('TRAN_018', '源账户与目标账户相同', 'P1', '异常', '100', '源账户和目标账户不能相同',
          '不合法，提示源账户和目标账户不能相同', '源账户：A；目标账户：A；金额：100',
          to_acc=ACC_A, steps=('1. 输入转账金额', '2. 选择与源账户相同的目标账户', '3. 提交')),
    _tran('TRAN_019', '目标账户不存在', 'P1', '异常', '100', '目标账户不存在',
          '不合法，提示目标账户不存在', '源账户：A；目标账户：D；金额：100',
          to_acc=ACC_D, steps=('1. 输入转账金额', '2. 输入不存在的目标账户', '3. 提交')),
]


# ============================================================
# 六、派生工具函数
# ============================================================
def cases_of(suite_key):
    return [c for c in CASES if c['suite'] == suite_key]


def module_of(suite_key):
    return next(m for m in MODULES if m['key'] == suite_key)


def pytest_node(case):
    mod = module_of(case['suite'])
    return f"{mod['test_file']}::{mod['test_func']}{case['pytest_node_suffix']}"


def summary():
    """汇总统计（按用例表实际统计）"""
    rows = []
    for m in MODULES:
        cs = cases_of(m['key'])
        rows.append({
            'module': m['module'],
            'rules': len([r for r in RULES if r['module'] == m['module']]),
            'equivalent': len(EQUIVALENCE[m['module']]),
            'cases': len(cs),
            'P0': len([c for c in cs if c['priority'] == 'P0']),
            'P1': len([c for c in cs if c['priority'] == 'P1']),
            'P2': len([c for c in cs if c['priority'] == 'P2']),
        })
    total = {
        'module': '合计',
        'rules': sum(r['rules'] for r in rows),
        'equivalent': sum(r['equivalent'] for r in rows),
        'cases': sum(r['cases'] for r in rows),
        'P0': sum(r['P0'] for r in rows),
        'P1': sum(r['P1'] for r in rows),
        'P2': sum(r['P2'] for r in rows),
    }
    return rows, total


# ============================================================
# 七、注入缺陷登记表（演示用）
# ------------------------------------------------------------
# 用例表按最新版文档与 xlsx，除第二节记录的落地口径与登录验证码扩展开关
# （LOGIN_016~019）外未作改动；失败来自被测系统侧注入的缺陷。
# 缺陷实现在 parabank_lite.py 中以 BUG-01 ~ BUG-03 标记，统一开关
# parabank_lite.INJECT_DEFECTS；置为 False 即恢复"完全符合文档"的系统，
# 60 条应当全绿。
# ============================================================
INJECTED_DEFECTS = [
    {
        'id': 'BUG-01',
        'title': '登录未区分"账号不存在"与"密码错误"',
        'rule': '2.1(5) 用户名必须已在系统中注册 / 2.1(6) 密码必须与注册时一致',
        'desc': '两种情况统一提示"用户名或密码错误"，与用例表要求的"账号不存在""密码错误"不符。',
        'layer': 'route', 'expect_prefix': 'ASSERT_',
        'cases': ['LOGIN_002', 'LOGIN_003'],
    },
    {
        'id': 'BUG-02',
        'title': '转账金额上限边界判断错误',
        'rule': '2.3(2) 金额范围 0.01 ~ 50000.00 元',
        'desc': '边界判断写成"≥ 50000 即超限"，恰好 50000.00 被误判为超过上限。',
        'layer': 'validator', 'expect_prefix': 'ASSERT_',
        'cases': ['TRAN_005'],
    },
    {
        'id': 'BUG-03',
        'title': '漏做"仅允许一个小数点"校验',
        'rule': '2.3(4) 金额只能包含数字和一个小数点',
        'desc': '去掉了小数点个数校验，1.2.3 这类输入落到小数位校验上，'
                '提示变成"金额最多保留2位小数"。',
        'layer': 'validator', 'expect_prefix': 'ASSERT_',
        'cases': ['TRAN_013'],
    },
]


def expected_failures():
    """预期失败的用例 {用例编号: 缺陷编号}。"""
    return {code: d['id'] for d in INJECTED_DEFECTS for code in d['cases']}


def defect_of(case_code):
    return next((d for d in INJECTED_DEFECTS if case_code in d['cases']), None)
