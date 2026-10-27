# Tinderbox 单机部署（个人装机的"上云"形态）

> 目标：把记忆库放到一台 VPS 上，自己在手机/笔记本都能用。
> **不是**多用户服务——只有一个主人，靠令牌区分"是不是你"。

---

## 0. 形态

```
浏览器 ──HTTPS──▶ Caddy（自动证书） ──HTTP──▶ tinderbox 服务（127.0.0.1:8777）
                                                    │
                                              /var/lib/tinderbox/
```

**应用只监听回环**，外网入口只有 Caddy。这样即使应用有漏洞，也碰不到公网。

---

## 1. 准备机器

```bash
# Debian/Ubuntu 为例
sudo apt update && sudo apt install -y python3 python3-venv git
sudo useradd -r -m -d /var/lib/tinderbox tinderbox
```

把仓库放到 `/opt/tinderbox`：

```bash
sudo git clone <你的仓库地址> /opt/tinderbox
sudo chown -R tinderbox:tinderbox /opt/tinderbox
```

---

## 2. 初始化数据

```bash
sudo -u tinderbox TB_DATA=/var/lib/tinderbox/data \
  python3 /opt/tinderbox/demo/tbc.py --data /var/lib/tinderbox/data init
```

会生成 `memory.db`、`l0/`、`logs/`、`config.toml`、`token.txt`。

**记下令牌**（登录看板要它）：

```bash
sudo cat /var/lib/tinderbox/data/token.txt
```

---

## 3. 装成 systemd 服务

复制 `deploy/tinderbox.service` 到 `/etc/systemd/system/`：

```bash
sudo cp /opt/tinderbox/deploy/tinderbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tinderbox
sudo systemctl status tinderbox --no-pager
```

日志：

```bash
journalctl -u tinderbox -f
tail -f /var/lib/tinderbox/data/logs/tinderbox.log
```

---

## 4. 反向代理 + 自动 HTTPS（Caddy）

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
# 按 https://caddyserver.com/docs/install 装 Caddy
```

复制 `deploy/Caddyfile` 到 `/etc/caddy/Caddyfile`，把 `tb.example.com` 改成你的域名：

```bash
sudo cp /opt/tinderbox/deploy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/tb.example.com/你的域名/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy 会自动申请证书。DNS 先指向这台机器，80/443 要放行。

---

## 5. 必须设的两个环境变量

在 `deploy/tinderbox.service` 里已有，按需改：

| 变量 | 作用 |
|---|---|
| `TB_DATA` | 数据目录（默认 `/var/lib/tinderbox/data`） |
| `TB_TRUST_PROXY=1` | **放在 Caddy 后面必须设**，否则所有请求都被当成来自本机 |
| `TB_ALLOW_IMPORT` | 默认不设；**不设就不能远程导入**（这是有意的） |

> `TB_TRUST_PROXY=1` 只应在"你确定前面只有自己的反代"时设置。
> 设错会让 `X-Forwarded-For` 可被伪造，导入的本机限制随之失效。

---

## 6. 备份（强烈建议）

```bash
sudo -u tinderbox TB_DATA=/var/lib/tinderbox/data \
  python3 /opt/tinderbox/demo/tbc.py --data /var/lib/tinderbox/data backup --keep 7
```

放进 cron（每天 3 点）：

```cron
0 3 * * * tinderbox TB_DATA=/var/lib/tinderbox/data python3 /opt/tinderbox/demo/tbc.py --data /var/lib/tinderbox/data backup --keep 7 >> /var/lib/tinderbox/backup.log 2>&1
```

备份在 `data/backup/<时间戳>/`，含 `manifest.json`（条目数与 sha256）。**不含 token**。

---

## 7. 健康检查

```bash
curl -s http://127.0.0.1:8777/healthz
# {"ok": true, "entries": 55}
```

不需要令牌，只暴露"活没活 + 有多少条"，可以接 Uptime Kuma 之类。

---

## 8. 安全检查清单

| 检查 | 命令 / 做法 |
|---|---|
| 应用只在回环 | `ss -ltnp \| grep 8777` 应显示 `127.0.0.1:8777` |
| 外网只能走 443 | 防火墙只放 22/80/443 |
| 令牌是长的 | `wc -c token.txt` ≈ 25 |
| 导入没被放开 | 从外网访问面板，点「导入」应提示"只允许在本机" |
| 备份真的能恢复 | 在测试目录跑一次 `restore` |
| 日志里没有密钥 | `grep -i "api_key\|token=" logs/tinderbox.log` 应为空 |

---

## 9. 升级

```bash
cd /opt/tinderbox && sudo -u tinderbox git pull
sudo systemctl restart tinderbox
```

数据库结构变更由 `ensure_columns()` / `ensure_tables()` 在启动时自动补齐，不需要手工迁移。
**升级前先备份。**

---

## 10. 这份部署方案明确不管的事

| 不做 | 原因 |
|---|---|
| 多用户 / 注册 | 产品定位是私人装机 |
| 水平扩容 | SQLite 单写者，多实例会打架 |
| 容器编排 | 单机一个进程，K8s 是过度设计 |
| 公网开放导入 | 会变成"任意文件读取"入口 |
