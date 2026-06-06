---
name: git-setup
description: Git version control + GitHub setup for dzat-b2b server project
metadata:
  type: project
---

# Git 版本控制设置

## 仓库信息
- GitHub: `https://github.com/Mx2003/dzat-hk`
- 分支: `main`
- 远程: `origin` → `https://github.com/Mx2003/dzat-hk.git`
- Token: 已配置在 `~/.git-credentials`（credential.helper=store）
- 标签: `stable` = 服务器正常运行状态（2026-06-06）

## .gitignore 排除项
- `.env` — 敏感信息（密码、API Key）
- `waha/webjs/` — Chrome 运行时缓存
- `backups/` — 备份文件
- `__pycache__/`, `*.pyc`, `node_modules/`
- `.env.example` — 不含密码的配置模板（已纳入 Git）

## 常用命令
```bash
cd /opt/dzat-b2b
git status                        # 查看改动
git add -A && git commit -m ".."  # 提交
git push                          # 推送到 GitHub
git log --oneline                 # 查看历史
git checkout stable               # 回退到稳定版本
git revert <commit>               # 撤销某次提交
```
