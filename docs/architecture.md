# 架构说明

## 为什么按旧项目拆层

旧项目 `qy-write` 的核心是“API 层接收请求，注册表选择工作流，Builder 构建 LangGraph，Node 完成具体业务，Memory 服务记录上下文”。这个项目沿用同样的边界，但减少外部依赖，避免学生大作业因为第三方 RAG、追踪平台或复杂数据库而难以运行。

## 短期记忆

短期记忆位于 `backend/app/graph/builders/base.py`：

- 每个 `StudentWritingGraphBuilder` 持有 `InMemorySaver`。
- 请求中的 `session_id` 会作为 LangGraph `thread_id`。
- 同一 `session_id` 的图状态会在进程内保留，适合展示“同一会话上下文延续”。

## 长期记忆

长期记忆位于 `backend/app/memory`：

- SQLite 文件默认写入 `backend/data/student_writer.sqlite3`。
- `conversation_sessions` 保存会话。
- `conversation_turns` 保存用户输入和智能体输出。
- `long_term_memories` 保存偏好、规则、经验、画像。
- `recall_memory_node` 在图开头召回相关长期记忆。
- `save_memory_node` 在图结尾把本次写作经验写回长期记忆。

## 答辩时可强调

- LangGraph 不只是顺序调用，而是有条件边：默认快速生成，用户开启“深度打磨”后才进入质量评估和深度修订节点。
- 短期记忆和长期记忆分别解决不同问题：短期用于当前会话状态，长期用于跨会话个性化。
- 前端展示了每个节点的输出，可以解释智能体的推理流程和工程可观测性。
- 模型层通过 OpenAI 兼容接口接入百炼云，当前使用 `glm-5.1`，后续替换模型不影响图结构。
