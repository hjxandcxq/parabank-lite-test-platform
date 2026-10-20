# -*- coding: utf-8 -*-
"""跨平台配置：项目路径 + 无头浏览器驱动。

Windows 与 Linux 通用，被 pytest_suites/*/conftest.py、para_test.py、
test_engine.py 共用，避免各文件重复硬编码 /opt/chrome 之类的容器路径。

可用环境变量覆盖：
    PB_BROWSER_BINARY  浏览器可执行文件路径（如 C:\\Program Files\\...\\chrome.exe）
    PB_DRIVER_PATH     驱动可执行文件路径（不设则由 Selenium Manager 自动匹配）
    PB_HEADLESS        1=无头（默认） 0=显示浏览器窗口
    PB_BASE_URL        被测系统根地址
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCREENSHOT_DIR = str(ROOT / 'screenshots')
DB_PATH = str(ROOT / 'parabank_test.db')

# 被测系统：ParaBank Lite（本机 Flask 服务，见文档"一、系统定义"）
BASE_URL = os.environ.get(
    'PB_BASE_URL', 'http://127.0.0.1:5000/parabank'
).rstrip('/')

_WIN_CANDIDATES = [
    os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]

_LINUX_CANDIDATES = [
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/microsoft-edge',
]


def find_browser():
    """返回 (浏览器类型, 可执行文件路径)，找不到返回 (None, None)。

    类型为 'chrome' 或 'edge'。
    """
    env_bin = os.environ.get('PB_BROWSER_BINARY', '').strip()
    if env_bin:
        if not os.path.exists(env_bin):
            raise RuntimeError(f'PB_BROWSER_BINARY 指向的文件不存在: {env_bin}')
        kind = 'edge' if 'msedge' in os.path.basename(env_bin).lower() else 'chrome'
        return kind, env_bin

    candidates = _WIN_CANDIDATES if sys.platform.startswith('win') else _LINUX_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            kind = 'edge' if 'msedge' in os.path.basename(path).lower() else 'chrome'
            return kind, path
    return None, None


def create_driver(headless=None, window_size='1600,900'):
    """创建无头浏览器驱动（本机 Chrome，没有则用 Edge）。"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.edge.service import Service as EdgeService

    kind, binary = find_browser()
    if kind is None:
        raise RuntimeError(
            '未找到 Chrome / Edge 浏览器。请安装 Chrome，'
            '或设置 PB_BROWSER_BINARY 指向浏览器可执行文件。'
        )

    if headless is None:
        headless = os.environ.get('PB_HEADLESS', '1') != '0'

    if kind == 'edge':
        options, service_cls = EdgeOptions(), EdgeService
    else:
        options, service_cls = ChromeOptions(), ChromeService

    if headless:
        options.add_argument('--headless=new')
    for arg in ('--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--disable-software-rasterizer', '--disable-extensions',
                f'--window-size={window_size}', '--log-level=3'):
        options.add_argument(arg)
    options.binary_location = binary

    driver_path = os.environ.get('PB_DRIVER_PATH', '').strip()
    # 不指定驱动路径时交给 Selenium Manager 自动下载匹配版本的驱动
    service = service_cls(driver_path) if driver_path else service_cls()

    driver = webdriver.Chrome(service=service, options=options) if kind == 'chrome' \
        else webdriver.Edge(service=service, options=options)
    driver.set_page_load_timeout(60)
    return driver


def save_screenshot(driver, name):
    """保存失败截图，返回路径（失败时返回 None）。"""
    from datetime import datetime

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(
        SCREENSHOT_DIR, f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    )
    try:
        driver.save_screenshot(path)
    except Exception:
        return None
    return path


def fail_with_screenshot(driver, name, message):
    """断言失败：先留截图再抛断言错误，供各套件复用。"""
    shot = save_screenshot(driver, name)
    if shot:
        raise AssertionError(f'{message}（失败截图：{shot}）')
    raise AssertionError(message)


def wait_any_message(driver, wait, case):
    """等页面上出现成功提示或错误提示（哪个先出现算哪个）。

    两个都没等到，说明元素缺失——留截图后按原异常类型抛出（平台归因 TIMEOUT_）。
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    try:
        return WebDriverWait(driver, wait).until(EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.msg.success')),
            EC.presence_of_element_located((By.CSS_SELECTOR, '.msg.error'))))
    except Exception as e:
        shot = save_screenshot(driver, case['code'])
        if shot and hasattr(e, 'msg'):
            e.msg = f'{e.msg}（失败截图：{shot}）'
        raise


def get_captcha_text(driver, base_url):
    """读取当前浏览器会话的验证码文本（登录自动化用）。

    验证码以 SVG 图片呈现，Selenium 无法直接"看"图；被测系统为此提供了
    测试专用只读接口 GET /parabank/captcha/text（环境变量
    PB_CAPTCHA_TEST_HOOK=0 可关闭）。这里复用浏览器的会话 Cookie 调用该接口，
    确保拿到的就是页面上那张图对应的验证码。
    """
    import requests

    cookies = {c['name']: c['value'] for c in driver.get_cookies()}
    resp = requests.get(f'{base_url}/captcha/text', cookies=cookies, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    text = (data.get('text') or '').strip()
    if not text:
        raise RuntimeError(f'未取到验证码（检查 PB_CAPTCHA_TEST_HOOK 是否被关闭）：{data}')
    return text


def fill_captcha(driver, base_url, field='captcha', transform=None):
    """把当前会话的验证码填进表单，返回填入的文本。

    transform 可传入 str.lower 等函数，用于验证"验证码不区分大小写"。
    """
    from selenium.webdriver.common.by import By

    text = get_captcha_text(driver, base_url)
    if transform:
        text = transform(text)
    el = driver.find_element(By.NAME, field)
    el.clear()
    el.send_keys(text)
    return text


def override_cases(cases):
    """给用例表数据套上平台参数覆盖（PB_<字段名> 环境变量）。

    平台上填了的字段才覆盖（如 PB_USERNAME、PB_AMOUNT）；
    留空即完全使用《ParaBank Lite 业务规则与测试用例设计》用例表的固定数据。
    """
    out = []
    for case in cases:
        form = dict(case['form'])
        for key in list(form):
            value = os.environ.get(f'PB_{key.upper()}', '').strip()
            if value:
                form[key] = value
        out.append({**case, 'form': form})
    return out
