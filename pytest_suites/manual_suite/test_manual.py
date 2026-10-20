# -*- coding: utf-8 -*-
"""手工验证台：按平台上填的参数跑一次真实浏览器操作。

执行方式：pytest 用例（本文件）+ Selenium 驱动无头 Edge 去点真实页面。

判定口径 —— 看"这次操作实际成没成"：
    注册：账号已在库里创建            → PASS（页面没给成功提示也会作为附注写出）
          页面给了错误提示            → FAIL，失败原因 = 系统提示原文
          账号最终没创建              → FAIL
    转账：源账户余额已按金额变化      → PASS（页面没给成功提示作为附注）
          页面给了错误提示            → FAIL，失败原因 = 系统提示原文
          余额没变                    → FAIL
    登录：已进入账户概览              → PASS
          页面给了错误提示            → FAIL，失败原因 = 系统提示原文

输入来自页面：参数以 PB_<字段名> 环境变量传入；观察结果写入 PB_RESULT_FILE，
平台存进 test_results.actual_result（"结果明细"的"实际提示"列）。
"""
import json
import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser_setup import fill_captcha, save_screenshot

WAIT = int(os.environ.get('PB_WAIT', '8'))
RESULT_FILE = os.environ.get('PB_RESULT_FILE', '').strip()
NO_FEEDBACK = '页面没有出现任何提示（既没有成功提示，也没有错误提示）'


def _env(key, default=''):
    return os.environ.get(f'PB_{key.upper()}', default).strip() or default


def _record(action, outcome, message, url=''):
    if RESULT_FILE:
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump({'action': action, 'outcome': outcome,
                       'message': message, 'url': url}, f, ensure_ascii=False)


def _finish(action, ok, message, url=''):
    """记录观察结果，并据此判定 PASS / FAIL"""
    _record(action, '成功' if ok else '失败', message, url)
    if not ok:
        pytest.fail(f'{action}失败：{message}')


# ---------- 查被测系统的库/余额，判断操作实际是否生效 ----------
def _user_exists(username):
    import parabank_lite as pb
    conn = pb.get_db()
    try:
        return bool(conn.execute('SELECT id FROM pb_users WHERE username=?',
                                 (username,)).fetchone())
    finally:
        conn.close()


def _balance(acc_no):
    import parabank_lite as pb
    conn = pb.get_db()
    try:
        row = conn.execute('SELECT balance FROM pb_accounts WHERE account_number=?',
                           (acc_no,)).fetchone()
        return row['balance'] if row else None
    finally:
        conn.close()


def _moved(before, after, amount):
    if before is None or after is None:
        return False
    try:
        return abs((before - after) - float(amount)) < 1e-6
    except (TypeError, ValueError):
        return False


# ---------- 等待页面反馈 ----------
def _screen_note(name, driver):
    shot = save_screenshot(driver, name)
    return f'{NO_FEEDBACK}' + (f'（截图：{shot}）' if shot else '')


def _wait_login(driver, name):
    """等跳转到账户概览或出现错误提示；返回 None 表示正常，否则返回"无反馈"说明"""
    try:
        WebDriverWait(driver, WAIT).until(
            lambda d: '/accounts' in d.current_url
            or d.find_elements(By.CSS_SELECTOR, '.msg.error'))
        return None
    except Exception:
        return _screen_note(name, driver)


def _wait_message(driver, name):
    """等成功提示或错误提示；返回 (元素, None) 或 (None, 无反馈说明)"""
    try:
        el = WebDriverWait(driver, WAIT).until(EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.msg.success')),
            EC.presence_of_element_located((By.CSS_SELECTOR, '.msg.error'))))
        return el, None
    except Exception:
        return None, _screen_note(name, driver)


def _is_success(el):
    return 'msg success' in (el.get_attribute('class') or '')


def _ui_login(driver, base_url, username, password):
    """打开登录页并提交；验证码由测试专用接口读取后填入。"""
    driver.get(f'{base_url}/login')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.NAME, 'username')))
    driver.find_element(By.NAME, 'username').send_keys(username)
    driver.find_element(By.NAME, 'password').send_keys(password)
    fill_captcha(driver, base_url)
    driver.find_element(By.ID, 'btn-login').click()


# ---------- 三个场景 ----------
def test_manual_login(driver, base_url):
    """用填写的用户名/密码登录一次"""
    username = _env('username')
    password = _env('password')

    _ui_login(driver, base_url, username, password)

    no_feedback = _wait_login(driver, 'manual_login')
    if no_feedback:
        _finish('登录', False,
                f'{no_feedback}；既没有跳转到账户概览，也没有错误提示',
                driver.current_url)
        return

    errors = driver.find_elements(By.CSS_SELECTOR, '.msg.error')
    if errors:
        _finish('登录', False, errors[0].text, driver.current_url)
    else:
        _finish('登录', True, '登录成功，已进入账户概览', driver.current_url)


def test_manual_register(driver, base_url):
    """用填写的信息注册一次（用户名留空时平台会自动造一个新用户）"""
    username = _env('username')

    driver.get(f'{base_url}/register')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.NAME, 'username')))
    for field in ('username', 'password', 'confirm'):
        el = driver.find_element(By.NAME, field)
        el.clear()
        el.send_keys(_env(field))
    driver.find_element(By.ID, 'btn-register').click()

    el, no_feedback = _wait_message(driver, 'manual_register')
    if el is not None:
        _finish('注册', _is_success(el), el.text, driver.current_url)
        return

    # 页面没反馈：查库看账号到底建了没
    if _user_exists(username):
        _finish('注册', True,
                f'注册成功：账号 {username} 已创建（注意：页面没有给出成功提示）',
                driver.current_url)
    else:
        _finish('注册', False,
                f'{no_feedback}；账号 {username} 未创建，注册没有生效',
                driver.current_url)


def test_manual_transfer(driver, base_url):
    """用填写的信息转一次账（登录用预置账号，可用 PB_LOGIN_USER 覆盖）"""
    username = _env('login_user', 'alice01')
    password = _env('login_password', 'Pass123')
    from_acc = _env('from_account', '10001')
    to_acc = _env('to_account', '10002')
    amount = _env('amount', '100')

    _ui_login(driver, base_url, username, password)
    no_feedback = _wait_login(driver, 'manual_transfer_login')
    if no_feedback:
        _finish('转账', False, f'转账前置登录未成功：{no_feedback}',
                driver.current_url)
        return

    driver.get(f'{base_url}/transfer')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.ID, 'amount')))
    try:
        Select(driver.find_element(By.NAME, 'from_account')).select_by_value(from_acc)
    except Exception:
        pass  # 账户不在下拉里就交给系统提示，不在这里判死
    to_account = driver.find_element(By.NAME, 'to_account')
    to_account.clear()
    to_account.send_keys(to_acc)
    amount_el = driver.find_element(By.ID, 'amount')
    amount_el.clear()
    amount_el.send_keys(amount)

    before = _balance(from_acc)
    driver.find_element(By.ID, 'btn-transfer').click()

    el, no_feedback = _wait_message(driver, 'manual_transfer')
    if el is not None:
        _finish('转账', _is_success(el), el.text, driver.current_url)
        return

    # 页面没反馈：查余额看钱到底动了没
    after = _balance(from_acc)
    if _moved(before, after, amount):
        _finish('转账', True,
                f'转账成功：源账户 {from_acc} 余额 {before:.2f} → {after:.2f}'
                f'（注意：页面没有给出成功提示）', driver.current_url)
    else:
        shown = '未知' if after is None else f'{after:.2f}'
        _finish('转账', False,
                f'{no_feedback}；源账户 {from_acc} 余额 {shown}，转账没有生效',
                driver.current_url)
