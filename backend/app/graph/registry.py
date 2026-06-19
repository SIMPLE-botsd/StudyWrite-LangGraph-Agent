from __future__ import annotations

from app.graph.builders import StudentWritingGraphBuilder


class WorkflowRegistry:
    def __init__(self):
        self._builders: dict[str, StudentWritingGraphBuilder] = {}

    def register(self, feature_name: str, builder: StudentWritingGraphBuilder) -> None:
        self._builders[feature_name] = builder

    def get_workflow(self, feature_name: str) -> StudentWritingGraphBuilder:
        return self._builders.get(feature_name) or self._builders["generate_assignment"]


registry = WorkflowRegistry()
registry.register("generate_assignment", StudentWritingGraphBuilder())
registry.register("polish_assignment", StudentWritingGraphBuilder())
registry.register("imitate_assignment", StudentWritingGraphBuilder())


def get_graph():
    return registry.get_workflow("generate_assignment")._build_graph(compile_with_checkpointer=False)
