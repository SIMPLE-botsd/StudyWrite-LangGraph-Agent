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
- `POST /writeapi/v1/imitate_writer`
- `GET /writeapi/v1/memory/overview?user_id=student-demo`
- `POST /writeapi/v1/memory/long-term`
- `GET /writeapi/v1/model/config`
- `GET /health`

三个写作接口默认返回 SSE：

```text
data: {"node":"plan_outline","event":"result","text":"..."}
```
