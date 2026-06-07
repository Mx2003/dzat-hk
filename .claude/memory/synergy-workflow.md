---
name: synergy-workflow
description: Dual-machine synergy workflow via /opt/dzat-synergy/ git repo with Windows Claude Code
metadata:
  type: project
---

# 双机协同工作机制

通过 `/opt/dzat-synergy/` 独立 git 仓库与 Windows Claude Code 传递任务。

## 会话开始时
```bash
cd /opt/dzat-synergy && git pull
```
读 `协同任务队列.md` 的 Windows → VPS 表，有任务就执行。

## 任务完成后
1. 把任务从待办表移到完成记录
2. ```bash
   cd /opt/dzat-synergy && git add -A && git commit -m "done: 描述" && git push
   ```

## 产生新任务时
写入 VPS → Windows 表 → commit + push

## 职责边界
- **VPS (我管)**: Docker 容器 / EspoCRM 配置 / Chatwoot+WAHA / Gateway / Nginx / MySQL+PostgreSQL / Redis
- **Windows (对方管)**: 获客采集 / 触达 / 看板 — 不要动这些代码

**Why:** 两台机器各司其职，通过 git 仓库异步传递任务，避免代码冲突。

**How to apply:** 每次会话开始时检查协同队列，有任务优先执行；做完或产生新任务及时 push。
