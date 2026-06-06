---
name: remaining-issues
description: Outstanding issues to fix in dzat-b2b — pending improvements
metadata:
  type: project
---

# 剩余待解决问题

Last updated: 2026-06-06

## 已完成 ✅
- ✅ 状态持久化到 Redis（重启不丢数据）
- ✅ 多语言支持（LLM 检测语言 + 同语言回复 + 对话中切语言）
- ✅ CRM 角色权限：业务员/经理/管理员 + 外贸组/内贸组
- ✅ 470 条线索轮询分配给外贸组成员
- ✅ Git 版本控制 + GitHub 远程仓库

## 待解决 🟡

### 1. 线索评分 → 外联系统跑起来
- 470 条线索的 `cLeadScore` 全部为空
- 外联器要求 ≥40 分才发消息 → 定时任务永远发 0 条
- **方案：** 用 DeepSeek 批量给线索打分，写入 EspoCRM。按国家/行业/关键词评估潜在价值

### 2. 转人工 → 自动分配客服
- 目前转人工只发企业微信通知，不会在 Chatwoot 里自动分给某个客服
- 刚配好的轮询分配规则可以跟转人工联动
- **方案：** 转人工时调用 Chatwoot API 把对话 assign 给对应团队的成员（按轮询）

### 3. RAG 知识库更新机制
- `gateway/knowledge/knowledge_base.json` 是写死的产品信息
- 价格/证书/产品线变更时需要手动改 JSON
- **方案：** 考虑从 EspoCRM 产品模块读取，或加一个管理接口

### 4. WA 号码映射无过期清理
- Redis 里 `wa_chat_ids` 哈希永久保留
- 长期来看会积累很多废弃映射
- **方案：** 加 TTL 或定期清理不活跃的映射

## 低优先级 🟢

### 5. Webhook 无鉴权
- WAHA webhook 和 Chatwoot webhook 端点无 HMAC 验证
- Chatwoot 提供了 HMAC token 但 Gateway 没用

### 6. LinkedIn/社媒外联渠道是占位符
- `channels.py` 里 LinkedInChannel 和 SocialDMChannel 返回 "pending Chrome Pool" 错误

### 7. 外联硬编码问题
- `scheduler.py` 里 `_push_dashboard` 函数硬编码了 API Key 和 WeChat URL
- `dispatcher.py` 里的 `ESPO_API_KEY` 应从配置读取

### 8. ChromaDB 未使用
- `requirements.txt` 装了 chromadb 但代码没用上
- RAG 目前用关键词 + DeepSeek，没有真正的向量检索

### 9. `_extract_phone` 逻辑问题
- `waha_bridge.py:79` 三元表达式总是 True（split 返回列表）

## 建议优先级
1. 线索评分（让外联系统产生实际价值）
2. 转人工自动分配（跟客服工作流打通）
3. 其他问题按需处理

## 相关记忆
- [[chatwoot-version-lock]] — Chatwoot 永远不升级 v3.12.0
- [[git-setup]] — Git 仓库配置
- [[change-workflow]] — 修改前先提交
