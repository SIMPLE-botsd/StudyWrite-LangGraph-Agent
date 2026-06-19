# RAGFlow 知识检索接入

项目已接入 RAGFlow Cloud，用于给 LangGraph 写作节点提供外部写作知识库。

## 配置

1. 登录 `https://cloud.ragflow.io/`。
2. 在 RAGFlow 控制台生成 API Key。
3. 复制 `backend/.env.example` 为 `backend/.env`，填写：

```env
RAGFLOW_BASE_URL=https://cloud.ragflow.io
RAGFLOW_API_KEY=你的_RAGFLOW_API_KEY
RAGFLOW_DEFAULT_TOP_K=6
```

不要把 RAGFlow 登录密码写进代码、README 或 `.env.example`。

## 初始化写作知识库

配置好 API Key 后，有两种方式创建示例写作知识库：

```bash
cd backend
python scripts/init_ragflow_writing_kb.py
```

也可以在页面左侧“知识检索”区域点击“初始化写作库”。脚本会上传三份 Markdown 种子资料：

- 大学课程论文写作方法库
- 实验报告与实践报告写作库
- AI学习方式与学术规范素材库

## 页面功能

- 启用知识库引用：运行写作工作流时，把 RAGFlow 检索片段加入 `retrieve_knowledge` 节点。
- 刷新：读取 RAGFlow 当前知识库列表。
- 上传：选择一个知识库后，把本地文件上传到 RAGFlow 并触发解析。
- 检索预览：在正式生成文章前，查看当前题目能召回哪些知识片段。

## 接口

后端新增接口都在 `/writeapi/v1/ragflow` 下：

- `GET /status`
- `GET /datasets`
- `POST /datasets`
- `POST /documents`
- `POST /retrieve`
- `POST /initialize-writing`

前端不会直接访问 RAGFlow，也不会暴露 API Key。
