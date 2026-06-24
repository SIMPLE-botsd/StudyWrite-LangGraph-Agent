# 大作业答辩说明

## 项目定位

本项目是面向学生课程写作的 LangGraph 智能体系统，不只是调用一次大模型，而是把写作任务拆成多个可解释节点。

## 技术点

- FastAPI 提供后端接口。
- Vue + Vite 提供写作工作台。
- LangGraph 负责工作流编排。
- `InMemorySaver` 负责短期会话状态。
- SQLite 负责长期记忆。
- 阿里云百炼提供真实大模型能力。

## 工作流亮点

1. `recall_memory` 读取会话历史和长期偏好。
2. `analyze_assignment` 拆解老师的作业要求。
3. `retrieve_knowledge` 根据作业类型匹配写作结构。
4. `plan_outline` 输出提纲。
5. `write_draft` 调用百炼模型生成初稿。
6. 默认直接整理最终结果，保证课堂演示速度。
7. 用户开启“深度打磨”后，`evaluate_draft` 给出结构、贴题、材料、语气、原创性评分，并进入 `revise_draft` 深度修订。
8. `save_memory` 写回长期记忆，下一次任务可召回。
