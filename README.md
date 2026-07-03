# china-vo 新文件夹邮件提醒

监控 `https://download.china-vo.org/psp/next/` 页面，当检测到新的 8 位日期命名文件夹（如 `20260629`）时，发送邮件提醒到 `recipient@foxmail.com`。

## 方案说明：电脑关机也能提醒

程序本身必须运行在**一直在线**的环境上。本仓库提供两种部署方式：

1. **GitHub Actions（推荐，免费）**：把代码推到 GitHub 仓库，由 GitHub 服务器定时执行，与你的电脑是否开机无关。
2. **云服务器 / 树莓派 / 旧手机**：把代码部署到始终开机的设备上，用 cron/systemd 定时任务运行。

## 文件说明

- `monitor.py`：核心监控脚本
- `.github/workflows/monitor.yml`：GitHub Actions 定时任务配置
- `.env.example`：本地测试用的环境变量模板
- `state.json`：已见过的文件夹列表（首次运行会自动生成）

## 使用方式

### 方式一：GitHub Actions（免费，无需自己的服务器）

1. 在 GitHub 新建一个仓库，把本文件夹内所有文件推上去。
2. 进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，依次添加以下 secrets：

   | Secret 名 | 说明 | 当前配置 |
   |-----------|------|----------|
   | `SMTP_HOST` | SMTP 服务器地址 | `smtp.gmail.com` |
   | `SMTP_PORT` | SMTP 端口 | `587` |
   | `SMTP_USER` | 发件邮箱账号 | `your-email@gmail.com` |
   | `SMTP_PASS` | 邮箱应用专用密码/授权码 | 你的 Gmail 应用专用密码 |
   | `FROM_EMAIL` | 发件人地址 | `your-email@gmail.com` |
   | `TO_EMAIL` | 收件人地址 | `recipient@foxmail.com` |

3. 进入 **Actions** 页面，找到 `Monitor china-vo new folders`，点击 **Run workflow** 手动运行一次。
4. 首次运行会初始化 `state.json`，不会发送邮件。之后每 3 小时自动检查一次。

> 注意：GitHub 规定，如果仓库连续 60 天没有任何提交/活动，定时任务会被自动暂停。可以偶尔手动触发一次，或定时往仓库里 push 一个空提交保持活跃。

### 方式二：云服务器 / 本地长期运行

1. 安装 Python 3.8+。
2. 复制环境变量文件并填写真实信息：

   ```bash
   cp .env.example .env
   # 编辑 .env
   ```

3. 本地测试运行：

   ```bash
   python monitor.py
   ```

4. 使用 cron 每 3 小时运行一次（Linux）：

   ```bash
   crontab -e
   ```

   添加：

   ```
   0 */3 * * * cd /path/to/邮件提醒 && python monitor.py >> monitor.log 2>&1
   ```

## 邮箱配置参考

| 邮箱 | SMTP 服务器 | 端口 | 密码类型 |
|------|------------|------|----------|
| Gmail | `smtp.gmail.com` | `587` | 应用专用密码 |
| QQ/foxmail | `smtp.qq.com` | `465` | 授权码 |
| 163 | `smtp.163.com` | `465` | 客户端授权码 |

## 提醒逻辑

- 解析网页中所有 `href="YYYYMMDD/"` 的文件夹。
- 与 `state.json` 中已记录的文件夹对比。
- 首次运行：初始化状态，不发送邮件。
- 之后：只要有新文件夹出现，立即发送邮件提醒，并更新 `state.json`。
