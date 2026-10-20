# -*- coding: utf-8 -*-
"""转账模块测试套件 —— 19 条用例（TRAN_001 ~ TRAN_019）。

用例数据来自 testcase_spec.py，与《ParaBank Lite 业务规则与测试用例设计（最新版）》
及《等价类划分与测试用例.xlsx》一致；提示文案与被测系统 parabank_lite.py 严格对齐。
前置条件：以预置账号 alice01 / Pass123 登录（该账号持有账户 A=10001、B=10002、C=10003），
每条用例前测试数据已复位。
"""
import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser_setup import (fail_with_screenshot, fill_captcha, override_cases,
                           save_screenshot, wait_any_message)
from testcase_spec import TRANSFER_USER, cases_of

CASES = override_cases(cases_of('transfer'))
WAIT = int(os.environ.get('PB_WAIT', '8'))   # 等待元素的秒数，可用 PB_WAIT 调整
TRANSFER_ACCOUNT, TRANSFER_PASSWORD = TRANSFER_USER


def _balance(acc_no):
    """读被测系统库里的账户余额（用例表要求校验余额变化时使用）。"""
    import parabank_lite as pb
    conn = pb.get_db()
    try:
        row = conn.execute('SELECT balance FROM pb_accounts WHERE account_number=?',
                           (acc_no,)).fetchone()
        return row['balance'] if row else None
    finally:
        conn.close()


def _message(driver, case, selector):
    """等元素出现；超时先留截图，再按原异常类型抛出（平台归因 TIMEOUT_）。"""
    try:
        el = WebDriverWait(driver, WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    except Exception as e:
        shot = save_screenshot(driver, case['code'])
        if shot and hasattr(e, 'msg'):
            e.msg = f'{e.msg}（失败截图：{shot}）'
        raise
    return el.text


def _login(driver, base_url):
    driver.get(f'{base_url}/login')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.NAME, 'username')))
    driver.find_element(By.NAME, 'username').send_keys(TRANSFER_ACCOUNT)
    driver.find_element(By.NAME, 'password').send_keys(TRANSFER_PASSWORD)
    fill_captcha(driver, base_url)          # 登录页已启用图形验证码
    driver.find_element(By.ID, 'btn-login').click()
    WebDriverWait(driver, WAIT).until(lambda d: '/accounts' in d.current_url)


@pytest.mark.parametrize('case', CASES, ids=[c['code'] for c in CASES])
def test_transfer(driver, base_url, case):
    """转账金额校验、账户校验与转账主流程（成功用例额外校验余额变化）。"""
    _login(driver, base_url)
    driver.get(f'{base_url}/transfer')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.ID, 'amount')))

    form = case['form']
    try:
        Select(driver.find_element(By.NAME, 'from_account')) \
            .select_by_value(form['from_account'])
    except Exception:
        pass  # 账户不在下拉里就交给系统提示，不在这里判死
    to_account = driver.find_element(By.NAME, 'to_account')
    to_account.clear()
    to_account.send_keys(form['to_account'])
    amount_el = driver.find_element(By.ID, 'amount')
    amount_el.clear()
    amount_el.send_keys(form['amount'])

    before_src = _balance(form['from_account'])
    before_dst = _balance(form['to_account'])
    driver.find_element(By.ID, 'btn-transfer').click()

    if case['success']:
        el = wait_any_message(driver, WAIT, case)
        msg = el.text
        if 'msg error' in (el.get_attribute('class') or ''):
            fail_with_screenshot(
                driver, case['code'],
                f"{case['code']} {case['title']}：预期转账成功，实际提示「{msg}」")
        if '转账成功' not in msg:
            fail_with_screenshot(driver, case['code'],
                                 f"{case['code']} 转账成功提示异常：「{msg}」")
        # 用例表要求：A 余额减少、B 余额增加（TRAN_001 / TRAN_017）
        amount = float(form['amount'])
        after_src = _balance(form['from_account'])
        after_dst = _balance(form['to_account'])
        src_ok = (before_src is not None and after_src is not None
                  and abs((before_src - after_src) - amount) < 1e-6)
        dst_ok = (before_dst is not None and after_dst is not None
                  and abs((after_dst - before_dst) - amount) < 1e-6)
        if not (src_ok and dst_ok):
            fail_with_screenshot(
                driver, case['code'],
                f"{case['code']} {case['title']}：余额变化不符——源账户 "
                f"{form['from_account']} {before_src} → {after_src}，目标账户 "
                f"{form['to_account']} {before_dst} → {after_dst}，转账金额 {amount}")
        return

    msg = _message(driver, case, '.msg.error')
    if case['expect_msg'] != msg.strip():
        fail_with_screenshot(
            driver, case['code'],
            f"{case['code']} {case['title']}：预期提示「{case['expect_msg']}」，实际「{msg.strip()}」")
