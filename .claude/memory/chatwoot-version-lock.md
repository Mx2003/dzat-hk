---
name: chatwoot-version-lock
description: Chatwoot must stay on v3.12.0 forever — never upgrade
metadata:
  type: project
---

# Chatwoot 版本永久锁定 v3.12.0

**永远不要升级 Chatwoot！**

- Docker 镜像：`chatwoot/chatwoot:v3.12.0`（不是 `latest`！）
- 原因：v4+ 引入了 Captain AI 功能，需要 `pgvector` 扩展，会炸掉 PostgreSQL 数据库
- 数据库已经在 2026-06-05 重置过一次，所有配置是重建的
- 每次修改 `docker-compose.yml` 时要特别确认 Chatwoot 镜像标签没有被改掉

**How to apply:** 修改 docker-compose.yml 时永远不碰 `image: chatwoot/chatwoot:v3.12.0` 这行
