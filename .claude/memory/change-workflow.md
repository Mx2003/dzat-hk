---
name: change-workflow
description: Safe workflow for modifying server — commit before changes, revert if broken
metadata:
  type: project
---

# 修改服务器的安全流程

**Why:** 服务器配置或代码改动可能导致服务异常，用 Git 可以随时回退。

**How to apply:**

## 改代码前
```bash
cd /opt/dzat-b2b
git status              # 看看当前有什么改动
git add -A
git commit -m "改之前的状态"
```

## 如果改坏了
```bash
git checkout stable     # 回到正常版本
# 或者撤销某个 commit
git revert HEAD         # 撤销最近一次提交
git push
```

## 定期备份
- 服务器正常运行时，更新 `stable` 标签：
```bash
git tag -d stable
git tag -a stable -m "服务器正常运行 - YYYY/MM/DD"
git push origin stable --force
```

## 注意
- Docker 容器改代码/配置后如果不工作，通过 `git diff` 看改了什么
- [[git-setup]] 有仓库地址和配置详情
- CLAUDE.md 有完整的架构文档
