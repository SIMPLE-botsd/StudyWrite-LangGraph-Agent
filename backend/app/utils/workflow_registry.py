from __future__ import annotations

from app.graph.registry import registry


class StudentWritingWorkflow:
    async def process(self, inputs):
        feature = inputs.get("feature", "generate_assignment")
        builder = registry.get_workflow(feature)
        async for chunk in builder.process(inputs):
            yield chunk


student_writing_workflow = StudentWritingWorkflow()
