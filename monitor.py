import os
import re
import sys
import json
import smtplib
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import requests

URL = "https://download.china-vo.org/psp/next/"
STATE_FILE = Path("state.json")
DATE_FOLDER_RE = re.compile(r'href="(\d{8})/"')

# 北京时间 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))

# 检查时间点：北京时间 0, 3, 6, 9, 12, 15, 18, 21 点
CHECK_HOURS = [0, 3, 6, 9, 12, 15, 18, 21]


def fetch_date_folders(retries=3):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
    }
    proxies = {"http": None, "https": None}
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                URL, headers=headers, proxies=proxies, timeout=30
            )
            resp.raise_for_status()
            return sorted(set(DATE_FOLDER_RE.findall(resp.text)))
        except requests.RequestException as e:
            last_error = e
            print(f"请求失败（{attempt}/{retries}）: {e}")
            if attempt < retries:
                time.sleep(2 ** attempt)

    raise last_error


def load_seen():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    return set()


def save_seen(folders):
    data = {"seen": sorted(folders)}
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_email(new_folders):
    import socket

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["TO_EMAIL"]

    urls = "\n".join(f"{URL}{name}/" for name in new_folders)
    subject = f"[NEXT] 观测提醒：{', '.join(new_folders)}"
    body = f"检测到以下新日期文件夹：\n\n{urls}\n\n-- \n自动监控提醒"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    # 设置全局 socket 超时（对 login/sendmail/quit 都生效）
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(60)
    server = None
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()

        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
    finally:
        socket.setdefaulttimeout(old_timeout)
        if server is not None:
            try:
                server.close()
            except Exception:
                pass


def main():
    now_beijing = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_beijing}] 开始检查...")

    folders = fetch_date_folders()
    print(f"获取到 {len(folders)} 个日期文件夹，最新: {folders[-1] if folders else '无'}")

    if not folders:
        print("未解析到任何日期文件夹，请检查页面结构是否变化。")
        return

    seen = load_seen()

    if not seen:
        print("首次运行，初始化状态文件，不发送邮件。")
        save_seen(folders)
        return

    new_folders = [name for name in folders if name not in seen]

    if new_folders:
        print(f"发现新文件夹: {new_folders}")
        print("开始发送邮件...")
        send_email(new_folders)
        print("邮件已发送。")
    else:
        print(f"没有新文件夹。当前最新: {folders[-1]}")

    print("保存状态文件...")
    save_seen(folders)
    print("完成。")


def get_next_check_time():
    now_beijing = datetime.now(BEIJING_TZ)
    current_hour = now_beijing.hour
    current_minute = now_beijing.minute

    # 找到下一个检查时间点
    next_hour = None
    for h in CHECK_HOURS:
        if h > current_hour or (h == current_hour and current_minute == 0):
            next_hour = h
            break

    if next_hour is None:
        # 今天所有时间点都已过，取明天的第一个时间点
        next_hour = CHECK_HOURS[0]
        next_time = now_beijing.replace(
            hour=next_hour, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
    else:
        next_time = now_beijing.replace(
            hour=next_hour, minute=0, second=0, microsecond=0
        )

    return next_time


def sleep_until_next_check():
    next_time = get_next_check_time()
    now_beijing = datetime.now(BEIJING_TZ)
    wait_seconds = (next_time - now_beijing).total_seconds()
    if wait_seconds > 0:
        print(f"下一次检查时间: {next_time.strftime('%Y-%m-%d %H:%M')} (北京时间)")
        print(f"等待 {wait_seconds / 60:.1f} 分钟...")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    if "--once" in sys.argv:
        print("手动检查模式")
        main()
        print("检查完成")
        sys.exit(0)

    print("NEXT 邮件提醒监控已启动")
    print(f"检查时间 (北京时间): {', '.join(f'{h}:00' for h in CHECK_HOURS)}")
    print("按 Ctrl+C 停止，使用 --once 参数可手动检查一次")

    while True:
        try:
            main()
        except Exception as e:
            print(f"检查出错: {e}")

        sleep_until_next_check()