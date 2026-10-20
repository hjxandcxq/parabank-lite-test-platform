# -*- coding: utf-8 -*-
"""登录模块测试套件 —— 19 条用例（LOGIN_001 ~ LOGIN_019）。

用例数据来自 testcase_spec.py，与《ParaBank Lite 业务规则与测试用例设计》
第四节用例表一致；提示文案与被测系统 parabank_lite.py 严格对齐。

验证码处理：图形验证码无法直接读图，自动化通过被测系统的测试专用只读接口
（GET /parabank/captcha/text，PB_CAPTCHA_TEST_HOOK=1 时启用）取当前会话的
验证码文本，再填入表单；LOGIN_016~019 分别验证空值、错误、大小写不敏感
和一次性使用。
"""
import os

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser_setup import (fail_with_screenshot, fill_captcha, override_cases,
                           save_screenshot)
from testcase_spec import cases_of

CASES = override_cases(cases_of('login'))
WAIT = int(os.environ.get('PB_WAIT', '8'))   # 等待元素的秒数，可用 PB_WAIT 调整
WRONG_CAPTCHA = '0000'                       # 验证码字符集不含 0，保证一定不匹配


def _fill_captcha_for_case(driver, base_url, case):
    """按用例的 captcha_mode 决定验证码怎么填（返回实际填入的值）。"""
    mode = case.get('captcha_mode', 'valid')
    if mode == 'blank':
        return ''
    if mode == 'wrong':
        el = driver.find_element(By.NAME, 'captcha')
        el.clear()
        el.send_keys(WRONG_CAPTCHA)
        return WRONG_CAPTCHA
    if mode == 'lower':
        return fill_captcha(driver, base_url, transform=str.lower)
    return fill_captcha(driver, base_url)


def _login_with_used_captcha(driver, base_url, case):
    """LOGIN_019：验证码一次性使用。

    第一次提交用正确验证码 + 错误密码，登录失败的同时验证码被作废、页面换发新码；
    第二次仍填旧验证码，系统应以「验证码错误」拒绝。
    """
    password = case['form']['password']
    wrong_password = password[:-1] + ('y' if password.endswith('x') else 'x')

    username = driver.find_element(By.NAME, 'username')
    pwd = driver.find_element(By.NAME, 'password')
    username.clear()
    username.send_keys(case['form']['username'])
    pwd.clear()
    pwd.send_keys(wrong_password)
    old_captcha = fill_captcha(driver, base_url)
    driver.find_element(By.ID, 'btn-login').click()
    _error_message(driver, case)   # 第一次提交失败即可，不校验具体文案

    username = driver.find_element(By.NAME, 'username')
    pwd = driver.find_element(By.NAME, 'password')
    captcha = driver.find_element(By.NAME, 'captcha')
    username.clear()
    username.send_keys(case['form']['username'])
    pwd.clear()
    pwd.send_keys(password)
    captcha.clear()
    captcha.send_keys(old_captcha)
    driver.find_element(By.ID, 'btn-login').click()

    msg = _error_message(driver, case).strip()
    if case['expect_msg'] != msg:
        fail_with_screenshot(
            driver, case['code'],
            f"{case['code']} {case['title']}：复用旧验证码，预期提示"
            f"「{case['expect_msg']}」，实际「{msg}」")


def _error_message(driver, case):
    """等错误提示出现；超时先留截图，再按原异常类型抛出（平台归因 TIMEOUT_）。"""
    try:
        el = WebDriverWait(driver, WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.msg.error')))
    except Exception as e:
        shot = save_screenshot(driver, case['code'])
        if shot and hasattr(e, 'msg'):
            e.msg = f'{e.msg}（失败截图：{shot}）'
        raise
    return el.text


@pytest.mark.parametrize('case', CASES, ids=[c['code'] for c in CASES])
def test_login(driver, base_url, case):
    """用户名/密码校验与登录主流程。"""
    driver.get(f'{base_url}/login')
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.NAME, 'username')))

    if case.get('captcha_mode') == 'reuse':
        _login_with_used_captcha(driver, base_url, case)
        return

    username = driver.find_element(By.NAME, 'username')
    password = driver.find_element(By.NAME, 'password')
    username.clear()
    username.send_keys(case['form']['username'])
    password.clear()
    password.send_keys(case['form']['password'])
    _fill_captcha_for_case(driver, base_url, case)
    driver.find_element(By.ID, 'btn-login').click()

    if case['success']:
        # 等"跳转到账户概览"或"出现错误提示"，哪个先到算哪个（避免白等满超时）
        try:
            WebDriverWait(driver, WAIT).until(
                lambda d: '/accounts' in d.current_url
                or d.find_elements(By.CSS_SELECTOR, '.msg.error'))
        except Exception as e:
            shot = save_screenshot(driver, case['code'])
            if shot and hasattr(e, 'msg'):
                e.msg = f'{e.msg}（失败截图：{shot}）'
            raise
        errors = driver.find_elements(By.CSS_SELECTOR, '.msg.error')
        if errors:
            fail_with_screenshot(
                driver, case['code'],
                f"{case['code']} {case['title']}：预期登录成功，实际提示「{errors[0].text}」")
        if not driver.find_elements(By.ID, 'accountTable'):
            fail_with_screenshot(driver, case['code'],
                                 f"{case['code']} 登录后未进入账户概览页")
        return

    msg = _error_message(driver, case)
    if case['expect_msg'] != msg.strip():
        fail_with_screenshot(
            driver, case['code'],
            f"{case['code']} {case['title']}：预期提示「{case['expect_msg']}」，实际「{msg.strip()}」")
