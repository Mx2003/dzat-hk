---
name: no-gitignore-protection
description: 不做 .gitignore 保护，默认全部文件提交（包括 .env、缓存等）
metadata:
  type: user
---

# 不做版本控制保护，默认全部提交

用户明确要求：不对项目文件做 `.gitignore` 保护，所有文件默认提交到 GitHub。

这包括：
- `.env`（含密码和 API Key）
- `__pycache__/`（Python 缓存）
- `waha/webjs/`（WAHA Chrome 运行时数据）
- `backups/`
- 一切文件

**Why:** 用户认为这是他们自己的私有仓库，不需要担心密码泄露到公有网络。方便完整备份，不怕丢东西。

**How to apply:** `git add -A` 时不要跳过任何文件。不要添加新的 `.gitignore` 排除规则。如果用户要加排除项，由用户主动提出。
