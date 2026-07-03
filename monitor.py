import os
import re
import json
import smtplib
import time
from email.mime.text import MIMEText
from pathlib import Path

import requests

URL = "https://download.china-vo.org/psp/next/"
STATE_FILE = Path("state.json")
DATE_FOLDER_RE = re.compile(r'href="(\d{8})/"')


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
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["TO_EMAIL"]

    urls = "\n".join(f"{URL}{name}/" for name in new_folders)
    subject = f"[china-vo] 发现新文件夹: {', '.join(new_folders)}"
    body = f"检测到以下新日期文件夹：\n\n{urls}\n\n-- \n自动监控提醒"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()

    with server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [to_email], msg.as_string())


def main():
    folders = fetch_date_folders()
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
        send_email(new_folders)
        print("邮件已发送。")
    else:
        print(f"没有新文件夹。当前最新: {folders[-1]}")

    save_seen(folders)


if __name__ == "__main__":
    main()
