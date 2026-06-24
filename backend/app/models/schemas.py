from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MemoryMixin(BaseModel):
    is_stream: bool = Field(True, description="是否使用 SSE 流式返回")
    use_memory: bool = Field(True, description="是否启用记忆")
    session_id: str = Field("demo-session", description="短期记忆 thread_id / 会话 ID")
    user_id: str = Field("student-demo", description="学生用户 ID")
    user_name: str = Field("学生", description="学生姓名")
    memory_k: int = Field(5, ge=1, le=10, description="长期记忆召回数量")
    use_rag: bool = Field(False, description="是否启用知识库检索")
    rag_dataset_ids: list[str] = Field(default_factory=list, description="知识库 ID 列表")
    rag_query: str = Field("", description="可选的知识库检索问题，为空时根据写作任务自动生成")
    rag_top_k: int = Field(6, ge=1, le=20, description="知识库检索片段数量")
    deep_polish: bool = Field(False, description="是否启用质量评估和深度修订")


class StudentWritingRequest(MemoryMixin):
    title: str = Field(..., description="作业题目或文章标题")
    assignment_type: str = Field("课程论文", description="课程论文、实验报告、读书报告、社会实践、演讲稿等")
    task_description: str = Field(..., description="老师布置的写作要求、评分标准或自己的想法")
    materials: str = Field("", description="课堂材料、数据、参考资料或草稿片段")
    style: str = Field("清晰、正式、学生化", description="期望语言风格")
    word_count: str = Field("1200", description="期望字数")
    academic_level: str = Field("本科课程作业", description="写作层级")
    rubric_focus: str = Field("结构完整、论证清楚、避免空话", description="评分关注点")
    use_llm: bool = Field(True, description="默认使用百炼云模型；无 API Key 时自动回退本地演示逻辑")


class PolishWritingRequest(MemoryMixin):
    title: str = Field("未命名润色任务", description="文章标题")
    content: str = Field(..., description="需要润色的原文")
    change_request: str = Field("提升逻辑与表达", description="润色要求")
    style: str = Field("自然、严谨、学生化", description="期望语言风格")
    assignment_type: str = Field("润色修改", description="任务类型")
    use_llm: bool = Field(True, description="默认使用百炼云模型；无 API Key 时自动回退本地演示逻辑")


class MemoryCreateRequest(BaseModel):
    user_id: str = Field("student-demo")
    kind: str = Field("preference", description="profile/preference/rule/experience")
    content: str = Field(..., description="长期记忆内容")
    tags: list[str] = Field(default_factory=list)
    source_session_id: str = Field("manual")
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssignmentSuggestionRequest(BaseModel):
    mode: str = Field("draft", description="draft/polish")
    current_title: str = Field("", description="当前表单中的题目，可为空")
    assignment_type: str = Field("课程论文", description="当前任务类型")
    user_id: str = Field("student-demo")


class AssignmentSuggestion(BaseModel):
    title: str
    assignment_type: str
    task_description: str
    materials: str = ""
    style: str = "清晰、正式、学生化"
    word_count: str = "1200"
    academic_level: str = "本科课程作业"
    rubric_focus: str = ""
    content: str = ""


class RagflowCreateDatasetRequest(BaseModel):
    name: str = Field(..., description="知识库名称")
    description: str = Field("", description="知识库说明")


class RagflowRetrieveRequest(BaseModel):
    question: str = Field(..., description="检索问题")
    dataset_ids: list[str] = Field(default_factory=list, description="知识库 ID")
    top_k: int = Field(6, ge=1, le=20, description="检索片段数量")


class ApiResponse(BaseModel):
    status: str = "success"
    message: str = ""
    data: Optional[Any] = None
