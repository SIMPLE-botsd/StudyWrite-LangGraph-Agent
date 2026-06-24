# Backend

FastAPI + LangGraph 后端。

## 运行

```bash
pip install -r requirements.txt
copy .env.example .env
python run.py
```

默认端口是 `8030`，避免和参考项目的 `8029` 冲突。

## 主要接口

- `POST /writeapi/v1/student_writer`
- `POST /writeapi/v1/polish_writer`
- `GET /writeapi/v1/ragflow/status`：知识库状态，默认返回本地 TurboVec/NumPy 检索状态
- `POST /writeapi/v1/ragflow/documents`：上传资料并写入本地知识库
- `POST /writeapi/v1/ragflow/retrieve`：检索本地知识库片段
- `GET /writeapi/v1/memory/overview?user_id=student-demo`
- `POST /writeapi/v1/memory/long-term`
- `GET /writeapi/v1/model/config`
- `GET /health`

默认 `KNOWLEDGE_BACKEND=local_turbovec`，知识库数据存入 `backend/data/turbovec_knowledge.sqlite3`。如果已安装 `turbovec` 扩展，会使用 `IdMapIndex`；未安装时自动降级为 NumPy 相似度检索。

三个写作接口默认返回 SSE：

```text
data: {"node":"plan_outline","event":"result","text":"..."}
```
