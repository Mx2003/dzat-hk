# Claude Code 记忆索引

项目文档已整合到 [CLAUDE.md](../CLAUDE.md)，恢复指南见 [RECOVERY.md](../RECOVERY.md)。

## 关键要点

- **Chatwoot = v3.12.0 永不动**: v4+ 需要 pgvector 会炸数据库
- **Gateway 改代码只 restart**: 代码卷挂载，不用 rebuild
- **时区 Asia/Hong_Kong**: 调度器使用 UTC+8
- **企微 Webhook 两个独立 key**: 看板 `c50b...` / 转人工 `c576...`
- **不做 .gitignore 保护**: 全部提交，唯一排除 `waha/webjs/`（root 权限）
- **协同仓库**: `/opt/dzat-synergy/`，每次会话开始 pull、结束 push
- **职责**: VPS 管 Docker/CRM/客服，Windows 管获客/触达

## Git

```bash
cd /opt/dzat-b2b
git add -A && git commit -m "描述" && git push
git checkout stable  # 回退
```
- GitHub: `https://github.com/Mx2003/dzat-hk`
- 协同: `/opt/dzat-synergy/` → `https://github.com/Mx2003/dzat-b2b-synergy`
