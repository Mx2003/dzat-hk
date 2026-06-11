# DZAT B2B — CRM + 客服 + WhatsApp 桥接

## 服务器

- IP: `43.161.238.10` | 腾讯云香港 | Ubuntu 24.04 LTS
- 项目路径: `/opt/dzat-b2b`
- Claude Code: v2.1.167 + DeepSeek v4-pro (`~/.claude/settings.json`)
- GitHub: `https://github.com/Mx2003/dzat-hk` (私有，main 分支)
- 协同仓库: `/opt/dzat-synergy/` → `https://github.com/Mx2003/dzat-b2b-synergy`

## 职责边界

- **VPS (本机)**: Docker 容器 / EspoCRM / Chatwoot+WAHA / Gateway / Nginx / DB
- **Windows (D:\DZAT-B2B)**: 获客采集 / 触达系统 / 控制台 — 不要动这些代码

---

## 10 个 Docker 容器

| 容器 | 镜像 | 端口 | 用途 |
|------|------|:---:|------|
| dzat-nginx | nginx:alpine | 80 | 反向代理 |
| dzat-espocrm | espocrm/espocrm | 8080 | CRM (PHP+Apache) |
| dzat-mysql | mysql:8.0 | — | EspoCRM 数据库 |
| dzat-chatwoot | chatwoot/chatwoot:**v3.12.0** | 3000 | 客服 (Rails) |
| dzat-chatwoot-sidekiq | chatwoot/chatwoot:**v3.12.0** | — | 后台任务 |
| dzat-postgres | postgres:15 | — | Chatwoot 数据库 |
| dzat-redis | redis:7-alpine | — | Chatwoot 缓存 + Gateway 状态 |
| dzat-waha | devlikeapro/waha | 3001 | WhatsApp 桥 |
| dzat-gateway | 自建 FastAPI | — | 桥接+RAG+调度 |
| dzat-uptime | louislam/uptime-kuma | 3002 | 监控 |

常用命令:
```bash
cd /opt/dzat-b2b
docker compose ps
docker logs dzat-gateway --tail 50
docker restart dzat-gateway         # 改代码后用这个（代码卷挂载，不用 rebuild）
docker exec dzat-espocrm php /var/www/html/command.php clear-cache
```

---

## 服务访问 & 凭证

| 服务 | URL | 账号 | 密码 |
|------|-----|------|------|
| EspoCRM | http://43.161.238.10:8080 | admin | DzatAdmin2024! |
| Chatwoot | http://43.161.238.10:3000 | dorianvale332@gmail.com | DzatAdmin2024! |
| WAHA | http://43.161.238.10:3001 | admin | 6724f395c61b4573987a32faf9f7c101 |
| Gateway | http://43.161.238.10/api/health | — | — |
| Uptime | http://43.161.238.10:3002 | — | — |

### API Keys

| 服务 | Key | Header |
|------|-----|--------|
| EspoCRM | `3f0f4ef281df645acdc6e30bf3d406ac` | `X-Api-Key` |
| Chatwoot | `8DWaDY5UDLfXXJ9rZT7Nf9ao` | `api_access_token` |
| WAHA | `02e9412ac92947d0a1412739957b0fd2` | `X-Api-Key` |
| DeepSeek | `sk-fe1125df69154871ac06d11548dfffa6` | Bearer token |

Chatwoot: Account ID=`1`, Inbox ID=`1` (API Channel, 非原生 WhatsApp). Webhook: `http://gateway:8000/api/chatwoot/webhook`
WAHA: Session=`default`, Bot 号码=`+86 177 2756 9685` (8617727569685@c.us)

---

## Nginx 路由

| 路径 | 上游 | 说明 |
|------|------|------|
| `/api` | gateway:8000 | Gateway API + WebSocket |
| `/crm/` | espocrm | 去掉 /crm/ 前缀 |
| `/chat/` | chatwoot-rails:3000 | 支持 WebSocket upgrade |
| `/waha/` | waha:3001 | 去掉 /waha/ 前缀 |
| `/monitor/` | uptime-kuma:3001 | 去掉 /monitor/ 前缀 |

---

## 消息流（客服链路）

```
WhatsApp → WAHA webhook → Gateway /api/waha/webhook
  → WahaBridge 多级匹配:
      ① find_lead_by_whatsapp(WA号码)
      ② Redis wa_lead_mapping（回头客 LD 映射）
      ③ 消息中提取邮箱/网站搜 CRM
      ④ 创建新 Lead + 初始化聊天状态字段
  → Chatwoot API 创建/追加对话 → webhook 回到 Gateway
  → RAG 引擎 (DeepSeek 多语言) 生成回复
  → WAHA 发回 WhatsApp + 写 CRM 字段 (cWaChatStatus/cWaMsgCount/cWaReply...)
  → 转人工条件: 3条消息 或 客户说 human/人工 → 企微通知
```

Chatwoot Inbox 是 API Channel，Gateway 是桥接中枢。

---

## AI 客服

- **RAG 引擎**: DeepSeek V4 Flash，FAQ 知识库 + 多语言自动检测回复
- **知识库**: `gateway/knowledge/knowledge_base.json` (6 模块: 公司/产品/商务/认证/联系/FAQ)
- **多语言**: 自动检测客户语言并以同语言回复，对话中可切换语言
- **转人工**: 3 条消息或明确请求 → 企微通知 (独立 webhook)
- **AI 控制**: Chatwoot 对话中发 `ai on/off` 切换

---

## 定时任务

| 任务 | 时间 | 状态 |
|------|------|:---:|
| discovery | 8/14/20 | 已关闭（获客移 Windows） |
| outreach | 10:00, 16:00 | 运行中（Asia/HK） |
| dashboard | 18:00 | 运行中（Asia/HK，HTML 图表截图→企微） |

---

## CRM: 角色权限 & 分配

| 角色 | 权限 | 用户 |
|------|------|------|
| 管理员 | 全部 | admin, maxiaowei, zouyuhang |
| 经理 (外贸) | 团队可见 | wangjiahui |
| 业务员 (外贸) | 只自己 | chenruipeng, guolisiqin |
| 业务员 (内贸) | 只自己 | mayi, penghaohang |

- 外贸组: 非中国客户 | 内贸组: 中国客户
- 分配规则: 轮询，470 条线索已分配
- 业务员只能看/编辑自己的 Lead/Contact/Account

---

## Gateway 架构

| 模块 | 文件 | 功能 |
|------|------|------|
| API 入口 | `main.py` | FastAPI + `/ws/events` WebSocket |
| WA 桥接 | `waha_bridge.py` | WAHA ↔ Chatwoot + 四级 Lead 匹配链 |
| RAG 引擎 | `rag_engine.py` | DeepSeek 多语言 FAQ + 回复生成 |
| EspoCRM | `espocrm_client.py` | Lead CRUD + 聊天状态更新 |
| 调度器 | `scheduler.py` | outreach 10/16 + dashboard 18 (HK) |
| 看板 | `dashboard_vps.py` | HTML+SVG 图表 → Playwright 截图 → 企微图片 |
| 企微通知 | `wechat_notify.py` | 转人工通知 (独立 webhook) + 看板推送 |
| 状态存储 | `state_store.py` | Redis 持久化 (对话/AI暂停/WA映射) |
| 外联 | `outreach/dispatcher.py` | 多渠道 DM 触达 + Lead 字段更新 |
| 获客 | `discovery/` | LangGraph 获客引擎 (API 手动触发) |

Gateway 代码卷挂载 `./gateway/app:/app/app`，改代码只需 `docker restart dzat-gateway`。

---

## 企微 Webhook

| 用途 | Key |
|------|-----|
| 看板推送 | `c50b51b4-a729-4cf0-9469-9bdf003b01da` |
| 转人工通知 | `c5761dbf-e7e9-40a2-a678-467ed51379de` |

---

## ⚠️ 关键警告

1. **Chatwoot 永远 v3.12.0** — 别碰 `latest`！v4+ 需要 pgvector 会炸数据库
2. Chatwoot DB 已重置过 (2026-06-05)，全部配置是重建的
3. **Gateway 改代码只用 restart**，不用 rebuild（代码卷挂载）
4. docker-compose.yml 改任何重要字段必须用 Git 记录
5. **不做 .gitignore 保护** — 所有文件默认提交（包括 .env/缓存），唯一排除 `waha/webjs/`（root 权限无法提交）
6. 任务通过 `/opt/dzat-synergy/` 与 Windows 传递：会话开始 pull → 执行 → push

---

## Git 工作流

```bash
cd /opt/dzat-b2b
git status                  # 看改动
git add -A && git commit -m "描述" && git push   # 提交+推送
git checkout stable         # 回退到稳定版
```

`stable` 标签指向当前稳定状态，重大改动后更新: `git tag -d stable && git tag -a stable -m "..." && git push origin stable --force`
