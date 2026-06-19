# API 示例

## 起草

```bash
curl -X POST http://127.0.0.1:8030/writeapi/v1/student_writer ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"人工智能对大学学习方式的影响\",\"assignment_type\":\"课程论文\",\"task_description\":\"结合课堂讨论分析影响并提出建议。\",\"materials\":\"AI 可辅助资料检索，但也可能造成依赖。\",\"session_id\":\"demo\",\"user_id\":\"student-demo\",\"is_stream\":false,\"use_llm\":true}"
```

## 记忆概览

```bash
curl "http://127.0.0.1:8030/writeapi/v1/memory/overview?user_id=student-demo"
```

## 模型状态

```bash
curl "http://127.0.0.1:8030/writeapi/v1/model/config"
```
