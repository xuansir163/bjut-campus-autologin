# -*- coding: utf-8 -*-
"""
北京工业大学 校园网自动登录（寝室光猫网 / 10.21.221.98 Dr.COM 认证）
=====================================================================
原理：检测到离线时，自动调用认证服务器的登录接口完成认证。

用法:
    python campus_login.py            # 在线则跳过，离线才登录
    python campus_login.py --status   # 只查看在线状态
    python campus_login.py --force    # 强制重新登录

账号密码请在同目录 config.json 中填写。
依赖：Python 3.6+（纯标准库，无需装任何第三方包）
"""
import json
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import re
import random
from pathlib import Path

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "config.json"
SER_HOST = "10.21.221.98"      # 认证服务器
EPORTAL_PORT = 801             # eportal 接口端口
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36")

# 服务类型 -> 账号后缀（登录页上选的"服务类型"对应关系）
SUFFIX_MAP = {
    "校园用户": "@campus",
    "移动": "@cmcc",
    "联通": "@unicom",
    "电信": "@telecom",
}


def log(msg):
    print(msg, flush=True)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get(url, timeout=6):
    """直连请求（绕过系统代理，避免代理软件干扰）"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def jsonp_parse(text):
    """从 callback({...}) / jsonpReturn({...}) 中提取 JSON"""
    m = re.search(r"\((\{.*\})\)", text, re.S)
    if not m:
        raise ValueError("响应不是 JSONP: " + text[:200])
    return json.loads(m.group(1))


def get_local_ip():
    """获取本机在校园网中的内网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((SER_HOST, 80))
        return s.getsockname()[0]
    finally:
        s.close()


def ncsi_ok():
    """Windows 标准联网探测：能拿到该内容 = 已真正联网"""
    try:
        return "Microsoft Connect Test" in http_get(
            "http://www.msftconnecttest.com/connecttest.txt", timeout=5)
    except Exception:
        return False


def session_online():
    """认证服务器上是否有本机的活动会话"""
    try:
        text = http_get("http://{}:{}/eportal/portal/online_list"
                        "?callback=t&terminal_type=1&lang=zh-cn"
                        .format(SER_HOST, EPORTAL_PORT))
        return '"online_ip"' in text
    except Exception:
        return False


def is_online():
    """双重判定：会话存在 或 外网探测通过"""
    return session_online() or ncsi_ok()


def do_login(account, password, suffix, local_ip):
    """
    调用登录接口。⚠️ 三个实测关键点（改错任何一处都会失败）：
    1. 账号必须带服务后缀（如 @campus）
    2. 密码明文传输（仅转码 URL 特殊字符，不做 md5/base64）
    3. lang=zh-cn 和 lang=zh 必须同时存在，缺 zh-cn 服务器回 Authentication fail
    """
    import random
    v = random.randint(1000, 9999)
    url = ("http://{}:{}/eportal/portal/login?callback=dr1003&login_method=1"
           "&user_account={}&user_password={}&wlan_user_ip={}&wlan_user_ipv6="
           "&wlan_user_mac=000000000000&wlan_ac_ip=&wlan_ac_name=&jsVersion=4.2.1"
           "&terminal_type=1&lang=zh-cn&v={}&lang=zh").format(
        SER_HOST, EPORTAL_PORT,
        urllib.parse.quote(account + suffix, safe=""),
        urllib.parse.quote(password, safe="!"),
        urllib.parse.quote(local_ip, safe=""),
        v)
    text = http_get(url, timeout=10)
    data = jsonp_parse(text)
    data["_raw"] = text[:200]
    return data


def do_logout():
    """登出当前 IP（用于 --force）"""
    url = "http://{}:{}/eportal/portal/logout?callback=dr1003&jsVersion=4.1&lang=zh-cn".format(
        SER_HOST, EPORTAL_PORT)
    try:
        return jsonp_parse(http_get(url, timeout=6))
    except Exception as e:
        log("登出请求异常(忽略): %s" % e)
        return None


def main():
    force = "--force" in sys.argv
    status_only = "--status" in sys.argv

    cfg = load_config()
    account = cfg["account"].strip()
    password = cfg["password"]
    suffix = SUFFIX_MAP.get(cfg.get("service", "校园用户"), "@campus")

    # 1. 是否在校园网环境（连不上认证服务器 = 不在校园网）
    try:
        local_ip = get_local_ip()
    except Exception:
        log("[SKIP] 连不上认证服务器({})，当前不在校园网环境".format(SER_HOST))
        return 0

    if status_only:
        log("[STATUS] {}".format("在线" if is_online() else "离线"))
        log("[IP] {}".format(local_ip))
        return 0

    if is_online() and not force:
        log("[OK] 已在线（{}），无需登录".format(local_ip))
        return 0

    if force and is_online():
        log("[..] 强制模式：先登出当前会话")
        do_logout()
        time.sleep(2)

    # 2. 登录（刚离线时认证服务器响应慢，失败自动重试）
    log("[..] 正在登录: {}{} (IP {})".format(account, suffix, local_ip))
    for attempt in range(1, 4):
        try:
            result = do_login(account, password, suffix, local_ip)
            if result.get("result") == 1:
                log("[OK] 登录成功!")
                return 0
            log("[..] 第{}次返回: {}".format(attempt, result.get("_raw", "")))
        except Exception as e:
            log("[..] 第{}次请求超时/出错({})，稍后重试...".format(attempt, type(e).__name__))
        time.sleep(3)
        if is_online():
            log("[OK] 登录成功(延迟确认)!")
            return 0

    log("[FAIL] 自动登录未成功。请打开 http://{}/a79.htm 手动登录一次，".format(SER_HOST))
    log("       若手动也失败请检查账号密码或服务类型是否填写正确。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
