# DZAT B2B 服务器恢复指南

> 换服务器时，把这个文件丢给 Claude Code 或任意 AI，复制下面的话即可。

---

## 给 AI 的指令（直接复制使用）

```
你的任务是根据当前目录下的 RECOVERY.md 文档，从头完成 DZAT B2B 服务器的恢复部署。

要求：
1. 严格按 RECOVERY.md 的步骤顺序执行，每步完成后验证再继续
2. 遇到问题自行排查修复，不要跳过任何步骤
3. 全部完成后运行第 11 步的验证命令，确认所有服务正常
4. 然后发一条 WhatsApp 消息给 +86 177 2756 9685 做端到端测试
5. 最后执行 git log 确认版本，更新 stable 标签

开始吧。
```

---

> 以下是 AI 执行的详细步骤。

## 前置条件

- Ubuntu 24.04 服务器，公网 IP 已配置
- 用户 `ubuntu`，有 sudo 权限
- 项目路径: `/opt/dzat-b2b`

---

## 第 1 步：安装 Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable docker --now
sudo usermod -aG docker ubuntu
newgrp docker   # 或退出重新登录
docker --version
docker compose version
```

## 第 2 步：克隆项目

```bash
# 生成 SSH Key
ssh-keygen -t ed25519 -C "dzat-server" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
# 把公钥添加到 https://github.com/settings/keys

# 克隆
sudo mkdir -p /opt
sudo chown ubuntu:ubuntu /opt
git clone git@github.com:Mx2003/dzat-hk.git /opt/dzat-b2b
cd /opt/dzat-b2b

# 如果使用 HTTPS token
# git clone https://github.com/Mx2003/dzat-hk.git /opt/dzat-b2b
# git config credential.helper store
```

## 第 3 步：确认 .env 文件

```bash
cat /opt/dzat-b2b/.env
```

确保包含以下变量（从仓库自动获取）:
```
SERVER_IP=<你的服务器IP>
MYSQL_ROOT_PASSWORD=Dzat2024!Secure
MYSQL_PASSWORD=EspoCRM2024!Pass
ESPO_ADMIN_USER=admin
ESPO_ADMIN_PASSWORD=DzatAdmin2024!
ESPO_API_KEY=3f0f4ef281df645acdc6e30bf3d406ac
POSTGRES_PASSWORD=Chatwoot2024!Pass
CHATWOOT_SECRET=8209f83247dce14c3a6addc222d5f029...
CHATWOOT_API_TOKEN=8DWaDY5UDLfXXJ9rZT7Nf9ao
DEEPSEEK_API_KEY=sk-fe1125df69154871ac06d11548dfffa6
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c50b51b4...
WECHAT_HANDOFF_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=c5761dbf...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=dorianvale332@gmail.com
SMTP_PASSWORD='nuvm xpoj vkjf slnr'
```

把 `SERVER_IP` 改成本机 IP。

## 第 4 步：拉起全部容器

```bash
cd /opt/dzat-b2b
docker compose up -d

# 等待 30 秒让数据库初始化
sleep 30

# 验证
docker compose ps
# 应该看到 10 个容器全部 Up
```

## 第 5 步：修复 WAHA 文件权限

```bash
# WAHA 的 Chrome 缓存由 root 创建，需要改权限
sudo chown -R ubuntu:ubuntu /opt/dzat-b2b/waha/ 2>/dev/null || true
```

## 第 6 步：配置 Chatwoot（如果数据库是空的）

登录 http://<IP>:3000（账号 admin@example.com / 密码在 `CHATWOOT_SECRET` 环境变量）

1. 创建 Account → 记下 Account ID (应为 1)
2. 创建 Inbox → 选 API Channel → 记下 Inbox ID
3. 设置 Webhook URL: `http://gateway:8000/api/chatwoot/webhook`
4. 配置 SMTP: smtp.gmail.com:587

## 第 7 步：配置 WAHA

WAHA 容器启动后自动恢复 default session。如果 session 丢失：

1. 登录 http://<IP>:3001 (账号 admin / 密码 6724f395c61b4573987a32faf9f7c101)
2. 创建新 session `default`
3. 扫描二维码绑定 +86 177 2756 9685
4. 配置 Webhook: `http://gateway:8000/api/waha/webhook`，勾选 message 事件

## 第 8 步：配置 EspoCRM 自定义字段

```bash
# 创建自定义字段
docker exec dzat-espocrm php /var/www/html/create_fields.php
```

## 第 9 步：运行 RBAC 设置（角色+团队+分配）

```bash
docker cp /opt/dzat-b2b/scripts/setup_crm_rbac.php dzat-espocrm:/var/www/html/scripts/
docker exec dzat-espocrm php /var/www/html/scripts/setup_crm_rbac.php
docker exec dzat-espocrm php /var/www/html/command.php clear-cache
docker exec dzat-espocrm php /var/www/html/command.php rebuild
```

## 第 10 步：分配现有线索

```bash
docker cp /opt/dzat-b2b/scripts/assign_leads.php dzat-espocrm:/var/www/html/scripts/
docker exec dzat-espocrm php /var/www/html/scripts/assign_leads.php
```

## 第 11 步：验证

```bash
# 健康检查
curl http://localhost/api/health

# EspoCRM API
curl -s http://localhost:8080/api/v1/Lead?maxSize=1 \
  -H "X-Api-Key: 3f0f4ef281df645acdc6e30bf3d406ac" | python3 -m json.tool | head -5

# Chatwoot API
curl -s http://localhost:3000/api/v1/accounts/1/inboxes \
  -H "api_access_token: 8DWaDY5UDLfXXJ9rZT7Nf9ao" | python3 -m json.tool | head -5

# WAHA
curl -s http://localhost:3001/api/sessions \
  -H "X-Api-Key: 02e9412ac92947d0a1412739957b0fd2"

# Gateway 日志
docker logs dzat-gateway --tail 10
```

## 第 12 步：测试 WhatsApp

用手机 WhatsApp 给 +86 177 2756 9685 发一条消息，然后：

```bash
docker logs dzat-gateway --tail 20
```

应该看到 RAW PAYLOAD、Contact found、RAG processing、WAHA OK。

---

## 备份恢复（可选：如果有数据库备份）

### MySQL (EspoCRM)
```bash
docker exec dzat-mysql mysql -uroot -p${MYSQL_ROOT_PASSWORD} espocrm < espocrm_backup.sql
```

### PostgreSQL (Chatwoot)
```bash
docker exec -i dzat-postgres psql -U chatwoot < chatwoot_backup.sql
```

---

## 关键注意事项

1. **Chatwoot = v3.12.0 永不动** — `docker-compose.yml` 里 `image: chatwoot/chatwoot:v3.12.0`，改成别的会炸数据库
2. **Gateway 代码卷挂载** — 改 `gateway/app/*.py` 后只需 `docker restart dzat-gateway`
3. **时区** — 调度器使用 `Asia/Hong_Kong`，UTC+8
4. **企微 Webhook** — 看板和转人工是两个不同的 key
5. **所有文件提交 GitHub** — 包括 .env、缓存，不做保护

---

## 恢复完成后

```bash
cd /opt/dzat-b2b
git log --oneline -3           # 确认版本
git tag -l "stable"            # 确认标签
```
