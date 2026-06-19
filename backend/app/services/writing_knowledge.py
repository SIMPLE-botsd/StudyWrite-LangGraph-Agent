from __future__ import annotations


ASSIGNMENT_GUIDES = {
    "课程论文": {
        "structure": ["引言", "问题提出", "理论或资料分析", "个人观点", "结论"],
        "focus": "论点要集中，材料要服务于论证，避免堆砌概念。",
    },
    "实验报告": {
        "structure": ["实验目的", "实验原理", "实验过程", "结果分析", "误差与改进", "结论"],
        "focus": "过程、数据和结论要能互相对应，分析不能只复述现象。",
    },
    "读书报告": {
        "structure": ["作品信息", "核心内容概括", "关键观点分析", "联系课程", "个人反思"],
        "focus": "概括要克制，重点放在观点理解和自己的思考。",
    },
    "社会实践": {
        "structure": ["实践背景", "实践过程", "观察发现", "问题分析", "建议与收获"],
        "focus": "要写出真实场景、具体问题和可执行建议。",
    },
    "演讲稿": {
        "structure": ["开场", "背景", "核心观点", "事例支撑", "号召或总结"],
        "focus": "语言要有节奏，观点要便于听众即时理解。",
    },
    "润色修改": {
        "structure": ["保留原意", "调整结构", "优化表达", "补足过渡"],
        "focus": "优先解决逻辑跳跃、表达重复和口语化问题。",
    },
    "仿写练习": {
        "structure": ["范文结构识别", "新主题替换", "表达节奏迁移", "原创性检查"],
        "focus": "只仿结构和节奏，不复制原句和具体素材。",
    },
}


def get_assignment_guide(assignment_type: str) -> dict[str, object]:
    return ASSIGNMENT_GUIDES.get(assignment_type, ASSIGNMENT_GUIDES["课程论文"])


def format_guide(assignment_type: str, rubric_focus: str = "") -> str:
    guide = get_assignment_guide(assignment_type)
    sections = " -> ".join(guide["structure"])
    focus = guide["focus"]
    extra = f"\n教师或自定义评分关注：{rubric_focus}" if rubric_focus else ""
    return f"推荐结构：{sections}\n写作重点：{focus}{extra}"
