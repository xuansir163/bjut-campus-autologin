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


def get_session(local_ip=None):
    """
    查询认证服务器上的在线会话，返回本机会话（dict）或 None。
    关键点：登出接口必须携带本机真实的 MAC 和账号，
    用假 MAC(000000000000) 登出会被服务器拒绝，返回"注销操作非本机终端"。

    优先按本机 IP 匹配（同一账号多设备同时在线时，避免误登出其他设备）；
    匹配不到再退回列表第一条。
    """
    url = ("http://{}:{}/eportal/portal/online_list"
           "?callback=t&terminal_type=1&lang=zh-cn").format(SER_HOST, EPORTAL_PORT)
    try:
        text = http_get(url, timeout=6)
    except Exception:
        return None
    if '"online_ip"' not in text:
        return None

    def normalize(row):
        def pick(*keys):
            for k in keys:
                v = row.get(k)
                if v:
                    return str(v)
            return ""
        return {
            "online_ip": pick("online_ip", "user_ip"),
            "user_mac": pick("online_mac", "user_mac", "mac"),
            "user_account": pick("user_account", "user_name", "account"),
            "online_time": pick("online_time"),
        }

    # 1) 正常 JSON 解析
    try:
        data = jsonp_parse(text)
        rows = data.get("list") or data.get("rows") or []
        if rows:
            chosen = None
            if local_ip:
                for item in rows:
                    if str(item.get("online_ip", "")) == str(local_ip):
                        chosen = item
                        break
            if chosen is None:
                chosen = rows[0]
            sess = normalize(chosen)
            sess["raw"] = text[:300]
            return sess if (sess["online_ip"] or sess["user_mac"]) else None
    except Exception:
        pass

    # 2) JSON 解析失败时退回正则提取（兼容畸形响应）
    def grab(*keys):
        for key in keys:
            m = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, text)
            if m and m.group(1):
                return m.group(1)
        return ""

    sess = {
        "online_ip": grab("online_ip", "user_ip"),
        "user_mac": grab("online_mac", "user_mac", "mac"),
        "user_account": grab("user_account", "user_name", "account"),
        "online_time": grab("online_time"),
        "raw": text[:300],
    }
    return sess if (sess["online_ip"] or sess["user_mac"]) else None


def session_online():
    """认证服务器上是否有本机的活动会话"""
    return get_session() is not None


def real_online():
    """真正的联网判定：只有外网探测通过才算通（会话存在 ≠ 有网）"""
    return ncsi_ok()


def is_online():
    """双重判定：会话存在 或 外网探测通过"""
    return session_online() or real_online()


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


def do_logout(sess, local_ip=""):
    """
    用会话里的真实 MAC + 账号登出（--force / 僵尸会话自愈都走这里）。
    返回 True 表示服务器确认已下线。
    """
    mac = re.sub(r"[^0-9a-fA-F]", "", sess.get("user_mac", "")).lower()
    account = sess.get("user_account", "")
    ip = sess.get("online_ip") or local_ip
    if not mac or not account:
        log("[WARN] 会话信息不全(MAC=%r 账号=%r)，无法定向登出" % (mac, account))
        return False

    url = ("http://{}:{}/eportal/portal/logout?callback=dr1003&login_method=1"
           "&user_account={}&wlan_user_ip={}&wlan_user_ipv6="
           "&wlan_user_mac={}&wlan_ac_ip=&wlan_ac_name=&jsVersion=4.1&lang=zh-cn"
           "&v={}&lang=zh"
           ).format(SER_HOST, EPORTAL_PORT,
                    urllib.parse.quote(account, safe=""),
                    urllib.parse.quote(ip, safe=""),
                    mac,
                    random.randint(1000, 9999))
    try:
        data = jsonp_parse(http_get(url, timeout=8))
    except Exception as e:
        log("[WARN] 登出请求异常: %s" % e)
        return False

    ok = data.get("result") == 1
    msg = data.get("msg") or data.get("message") or ""
    if ok:
        log("[OK] 已登出会话 (MAC %s)" % mac)
    else:
        log("[WARN] 登出被拒: %s" % (msg or data))
    return ok


def force_logout(local_ip=""):
    """强登出：查真实会话 → 定向登出 → 复查，最多重试 2 轮"""
    for i in range(1, 3):
        sess = get_session(local_ip)
        if not sess:
            log("[OK] 服务器上已无本机会话")
            return True
        if do_logout(sess, local_ip):
            time.sleep(1.5)
            if not session_online():
                return True
            log("[..] 登出后会话仍在，重试(%d/2)" % i)
        else:
            time.sleep(1.5)
    return not session_online()


def main():
    force = "--force" in sys.argv
    status_only = "--status" in sys.argv

    cfg = None
    if not status_only:
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
        sess = get_session(local_ip)
        net = real_online()
        if sess and net:
            state = "在线（正常）"
        elif sess and not net:
            state = "假在线（有会话但无网，建议 --force）"
        elif net:
            state = "在线（无会话记录但能上网）"
        else:
            state = "离线"
        log("[STATUS] {}".format(state))
        log("[IP] {}".format(local_ip))
        if sess:
            log("[SESSION] ip=%s mac=%s account=%s"
                % (sess["online_ip"], sess["user_mac"], sess["user_account"]))
        return 0

    # 2. 真正在线（会话在 + 外网通）才跳过
    sess = get_session(local_ip)
    net = real_online()
    if net and not force:
        log("[OK] 已在线（{}），无需登录".format(local_ip))
        return 0

    # 3. 需要重新认证的三种情况
    if force:
        log("[..] 强制模式：按真实 MAC/账号登出当前会话")
        if not force_logout(local_ip):
            log("[WARN] 登出未确认成功，仍继续尝试登录")
    elif sess and not net:
        # ★ 核心修复：僵尸会话（服务器说有会话，但实际没网）
        # 不清掉它，登录接口只会回「512 已在线」，脚本会误报成功
        log("[..] 检测到僵尸会话（有会话但无网），自动登出后重登")
        force_logout(local_ip)
    time.sleep(1.5)

    # 4. 登录（刚离线时认证服务器响应慢，失败自动重试）
    log("[..] 正在登录: {}{} (IP {})".format(account, suffix, local_ip))
    for attempt in range(1, 4):
        try:
            result = do_login(account, password, suffix, local_ip)
            if result.get("result") == 1:
                log("[OK] 登录成功!")
                return 0
            raw = result.get("_raw", "")
            if "512" in raw or "已在线" in raw:
                # 服务器仍认为在线：本轮先清会话，下一轮再登
                log("[..] 服务器返回「已在线」(512)，清会话后重试")
                force_logout(local_ip)
            else:
                log("[..] 第{}次返回: {}".format(attempt, raw))
        except Exception as e:
            log("[..] 第{}次请求超时/出错({})，稍后重试...".format(attempt, type(e).__name__))
        time.sleep(3)
        # ★ 延迟确认必须验"真联网"，不能只看会话存在（否则又是一次假成功）
        if real_online():
            log("[OK] 登录成功(延迟确认)!")
            return 0

    if session_online():
        log("[FAIL] 会话显示在线，但外网仍不通：可能是僵尸会话或账号被限速。")
        log("       请打开 http://{}/a79.htm 手动注销再登录一次。".format(SER_HOST))
    else:
        log("[FAIL] 自动登录未成功。请打开 http://{}/a79.htm 手动登录一次，".format(SER_HOST))
        log("       若手动也失败请检查账号密码或服务类型是否填写正确。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
