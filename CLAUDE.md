# DZAT B2B 服务器 — CRM + 客服

## 架构分工

```
服务器 (本项目 /opt/dzat-b2b)          本地 (D:\DZAT-B2B, Trae)
┌──────────────────────────┐         ┌─────────────────────────┐
│ EspoCRM :8080 (CRM中枢)  │ ←POST   │ 获客引擎                 │
│ MySQL                    │ 线索    │ Google/社媒/关键词        │
│                          │         │                         │
│ Chatwoot :3000 (客服)    │  GET→   │ 触达系统                 │
│ WAHA :3001 (WhatsApp桥)  │ 线索    │ WA/Email/LinkedIn/社媒   │
│ Gateway (RAG+桥接)       │         │                         │
│ PostgreSQL + Redis       │         │ 控制台 :8520             │
│ Uptime :3002 (监控)      │         │                         │
└──────────────────────────┘         └─────────────────────────┘
```

## 服务器

- IP: `43.161.238.10`
- 系统: Ubuntu 24.04.4 LTS，腾讯云香港
- 路径: `/opt/dzat-b2b`
- Claude Code: v2.1.167 + DeepSeek v4-pro 已配置 (`~/.claude/settings.json`)

## 10 个 Docker 容器

| 容器 | 镜像 | 端口 | 用途 |
|------|------|:---:|------|
| dzat-nginx | nginx:alpine | 80 | 反代 |
| dzat-espocrm | espocrm/espocrm | 8080 | CRM (PHP+Apache) |
| dzat-mysql | mysql:8.0 | — | EspoCRM DB |
| dzat-chatwoot | chatwoot/chatwoot:**v3.12.0** | 3000 | 客服 (Rails) |
| dzat-chatwoot-sidekiq | chatwoot/chatwoot:**v3.12.0** | — | 后台任务 |
| dzat-postgres | postgres:15 | — | Chatwoot DB |
| dzat-redis | redis:7-alpine | — | Chatwoot 缓存 |
| dzat-waha | devlikeapro/waha | 3001 | WhatsApp 桥 |
| dzat-gateway | 自建 FastAPI | — | 桥接+RAG+调度 |
| dzat-uptime | louislam/uptime-kuma | 3002 | 监控 |

```bash
cd /opt/dzat-b2b
docker compose ps        # 查看所有容器状态
docker logs dzat-gateway --tail 50
docker restart dzat-gateway
```

## 服务访问

| 服务 | URL | 账号 | 密码 |
|------|-----|------|------|
| EspoCRM | http://43.161.238.10:8080 | admin | DzatAdmin2024! |
| Chatwoot | http://43.161.238.10:3000 | dorianvale332@gmail.com | DzatAdmin2024! |
| WAHA | http://43.161.238.10:3001 | admin | 6724f395c61b4573987a32faf9f7c101 |
| Gateway | http://43.161.238.10/api/health | — | — |
| Uptime | http://43.161.238.10:3002 | — | — |

## API Keys

| 服务 | Key | Header |
|------|-----|--------|
| EspoCRM | `3f0f4ef281df645acdc6e30bf3d406ac` | `X-Api-Key` |
| Chatwoot | `8DWaDY5UDLfXXJ9rZT7Nf9ao` | `api_access_token` |
| WAHA | `02e9412ac92947d0a1412739957b0fd2` | `X-Api-Key` |
| DeepSeek | `sk-fe1125df69154871ac06d11548dfffa6` | Bearer token |

### Chatwoot API 配置

- Account ID: `1`
- Inbox ID: `1` (WhatsApp Bridge, API Channel 类型)
- Webhook URL: `http://gateway:8000/api/chatwoot/webhook`

### WAHA 配置

- Session: `default` — WORKING
- Bot 号码: `+86 177 2756 9685` (8617727569685@c.us)
- API Key: `02e9412ac92947d0a1412739957b0fd2`

## 消息流（客服链路）

```
WhatsApp → WAHA webhook → Gateway (/api/waha/webhook)
  → Chatwoot API 创建/追加对话
  → Agent 在 Chatwoot 回复
  → Chatwoot webhook → Gateway (/api/chatwoot/webhook)
  → WAHA 发回 WhatsApp
```

Chatwoot Inbox 是 API Channel 类型（id=1），不是原生 WhatsApp inbox。Gateway 充当桥接中枢。

## Gateway 部署

Gateway 代码卷挂载到 `./gateway/app:/app/app`，改代码只需 restart：

```bash
# 本地上传 (从 d:/DZAT-B2B-Claude/server/)
scp -i d:/dzatcloudpem/dzatcloude.pem gateway/app/XXX.py ubuntu@43.161.238.10:/opt/dzat-b2b/gateway/app/XXX.py

# 重启
ssh -i d:/dzatcloudpem/dzatcloude.pem ubuntu@43.161.238.10 "docker restart dzat-gateway"

# 看日志
ssh -i d:/dzatcloudpem/dzatcloude.pem ubuntu@43.161.238.10 "docker logs dzat-gateway --tail 20"
```

## 定时任务 (scheduler.py)

```python
# discovery: 8/14/20点 → 已关闭 (获客计划移到本地)
# outreach:  10/16点  → 已关闭 (触达计划移到本地)
# dashboard: 18点     → 暂停
```

获客和触达已迁移到本地 `D:\DZAT-B2B`，服务器只跑客服。

## AI 客服控制

在 Chatwoot 对话中输入：

| 命令 | 效果 |
|------|------|
| `ai off` / `ai pause` | 暂停 AI 自动回复 |
| `ai on` / `ai resume` | 恢复 AI 自动回复 |
| Agent 手动回复客户 | 自动暂停 AI |

状态存 Gateway 内存，重启丢失。

## EspoCRM 线索结构

标准字段: name, firstName, lastName, website, emailAddress, phoneNumber, addressCountry, status, description

自定义字段 (c前缀):
- `cLeadScore` (int) — AI 评分 0-100
- `cScoreGrade` (varchar) — S/A/B/C
- `cSourceKeywords` (varchar) — 搜索关键词
- `cDeepReport` (text) — AI 深度分析
- `cWhatsapp` (varchar) — WA 号码
- `cLeadCountry` (varchar) — 国家

## ⚠️ 关键警告

1. **Chatwoot 永远 v3.12.0** — 别碰 `latest`！v4+ 的 Captain AI 需要 pgvector，会炸数据库
2. **Chatwoot DB 已重置过** (2026-06-05)，全部配置是重建的
3. **docker-compose.yml 改了什么重要字段**立即记录，尤其是 Chatwoot 镜像标签
4. **Gateway 改代码只用 restart**，不用 rebuild（代码是卷挂载的）

---

## Windows 协同规则

通过 `/opt/dzat-synergy/`（独立 git 仓库 `dzat-b2b-synergy`）与 Windows Claude Code 协同：

### 会话开始时
```bash
cd /opt/dzat-synergy && git pull
```
读 `协同任务队列.md` 的 Windows → VPS 表，有任务就执行。

### 任务完成后
1. 勾掉任务，移到完成记录
2. ```bash
   cd /opt/dzat-synergy && git add -A && git commit -m "done: 描述" && git push
   ```

### 产生新任务时
写入 VPS → Windows 表 → commit + push

### 职责边界
- **你管**: Docker 容器 / EspoCRM 配置 / Chatwoot+WAHA / Gateway / Nginx / MySQL+PostgreSQL
- **Windows 管**: 获客采集 / 触达 / 看板 — 不要动这些代码
