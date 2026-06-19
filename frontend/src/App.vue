<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand-block">
        <p class="eyebrow">LangGraph Coursework Agent</p>
        <h1>StudyWrite 学生写作智能体</h1>
        <p class="subtitle">
          面向课程论文、报告、润色与仿写的多节点写作工作流，支持短期记忆和长期记忆。
        </p>
      </div>

      <div class="top-actions">
        <ModelStatus :config="modelConfig" />
        <ModeTabs v-model="mode" />
      </div>
    </header>

    <section class="workspace">
      <aside class="left-rail">
        <ConfigPanel
          v-model="form"
          :mode="mode"
          :running="running"
          :suggesting="suggesting"
          :notice="notice"
          @run="runWorkflow"
          @suggest="suggestForm"
        />
      </aside>

      <section class="main-stage">
        <ResultEditor v-model="result" />
      </section>

      <aside class="right-rail">
        <WorkflowTrace :nodes="traceNodes" :running="running" />
        <MemoryPanel
          :overview="memoryOverview"
          :user-id="form.user_id"
          @refresh="refreshMemory"
          @add="addMemory"
        />
      </aside>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue';
import ConfigPanel from './components/ConfigPanel.vue';
import MemoryPanel from './components/MemoryPanel.vue';
import ModeTabs from './components/ModeTabs.vue';
import ModelStatus from './components/ModelStatus.vue';
import ResultEditor from './components/ResultEditor.vue';
import WorkflowTrace, { type TraceNode } from './components/WorkflowTrace.vue';
import {
  createMemory,
  fetchAssignmentSuggestion,
  fetchMemoryOverview,
  fetchModelConfig,
  streamWorkflow,
  type MemoryOverview,
  type ModelConfig,
  type WorkflowChunk,
} from './services/api';

const mode = ref('draft');
const running = ref(false);
const suggesting = ref(false);
const result = ref('');
const traceNodes = ref<TraceNode[]>([]);
const memoryOverview = ref<MemoryOverview | null>(null);
const modelConfig = ref<ModelConfig | null>(null);

const form = reactive<Record<string, any>>({
  user_id: 'student-demo',
  user_name: '学生',
  session_id: 'coursework-demo',
  title: '人工智能对大学学习方式的影响',
  assignment_type: '课程论文',
  task_description: '结合课堂讨论和个人学习体验，分析生成式人工智能对大学生学习方式的影响，并提出合理使用建议。',
  materials: '课堂提到：AI 可以提升资料检索和初稿生成效率，但也可能造成依赖、误判资料可信度、削弱原创思考。',
  style: '清晰、正式、学生化',
  word_count: '1200',
  academic_level: '本科课程作业',
  rubric_focus: '观点明确，论证有材料支撑，体现个人反思，避免直接照搬 AI 输出。',
  content: '人工智能现在很流行，很多同学都会用它写作业。它有好处也有坏处，所以我们要正确看待。',
  reference_text: '学习并不是简单地接收结论，而是在不断提问、验证和修正中形成自己的理解。',
  use_memory: true,
  use_llm: true,
  memory_k: 5,
  use_rag: false,
  rag_dataset_ids: [],
  rag_query: '',
  rag_top_k: 6,
});
const notice = ref('');

watch(mode, () => {
  if (mode.value === 'polish') {
    form.assignment_type = '润色修改';
    form.title = form.title || '课程作业润色';
  } else if (mode.value === 'imitate') {
    form.assignment_type = '仿写练习';
    form.title = form.title || '仿写练习';
  } else {
    form.assignment_type = '课程论文';
  }
});

onMounted(() => {
  refreshMemory();
  refreshModelConfig();
});

async function runWorkflow() {
  running.value = true;
  notice.value = 'LangGraph 工作流正在运行...';
  result.value = '';
  traceNodes.value = [];
  const endpoint = mode.value === 'polish'
    ? '/polish_writer'
    : mode.value === 'imitate'
      ? '/imitate_writer'
      : '/student_writer';

  try {
    await streamWorkflow(endpoint, buildPayload(), handleChunk);
    await refreshMemory();
    notice.value = '工作流已完成。';
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error);
  } finally {
    running.value = false;
  }
}

function buildPayload() {
  const base = {
    user_id: form.user_id,
    user_name: form.user_name,
    session_id: form.session_id,
    title: form.title,
    assignment_type: form.assignment_type,
    style: form.style,
    use_memory: form.use_memory,
    use_llm: form.use_llm,
    memory_k: form.memory_k,
    use_rag: form.use_rag,
    rag_dataset_ids: form.rag_dataset_ids,
    rag_query: form.rag_query,
    rag_top_k: form.rag_top_k,
  };

  if (mode.value === 'polish') {
    return {
      ...base,
      content: form.content,
      change_request: form.task_description,
    };
  }

  if (mode.value === 'imitate') {
    return {
      ...base,
      reference_text: form.reference_text,
      task_description: form.task_description,
      imitation_degree: '结构仿写，不复制原句',
    };
  }

  return {
    ...base,
    task_description: form.task_description,
    materials: form.materials,
    word_count: form.word_count,
    academic_level: form.academic_level,
    rubric_focus: form.rubric_focus,
  };
}

function handleChunk(chunk: WorkflowChunk) {
  const existing = traceNodes.value.find((item) => item.id === chunk.node);
  const nextState = chunk.event === 'error' ? 'error' : chunk.event === 'start' ? 'start' : 'done';
  const preview = chunk.text.length > 180 ? `${chunk.text.slice(0, 180)}...` : chunk.text;

  if (existing) {
    existing.state = nextState;
    existing.preview = preview;
  } else {
    traceNodes.value.push({
      id: chunk.node,
      name: nodeName(chunk.node),
      state: nextState,
      preview,
    });
  }

  if (chunk.node === 'render' && chunk.typy === 'result') {
    result.value = chunk.text;
  }
}

function nodeName(id: string) {
  const map: Record<string, string> = {
    recall_memory: '读取记忆',
    analyze_assignment: '理解要求',
    retrieve_knowledge: '匹配知识',
    plan_outline: '规划提纲',
    write_draft: '生成初稿',
    evaluate_draft: '质量评估',
    revise_draft: '自动修订',
    render: '整理结果',
    save_memory: '写入记忆',
  };
  return map[id] || id;
}

async function refreshMemory() {
  memoryOverview.value = await fetchMemoryOverview(form.user_id);
}

async function refreshModelConfig() {
  modelConfig.value = await fetchModelConfig();
}

async function addMemory(payload: { kind: string; content: string }) {
  await createMemory({
    user_id: form.user_id,
    kind: payload.kind,
    content: payload.content,
    tags: ['手动添加'],
    source_session_id: form.session_id,
  });
  await refreshMemory();
}

async function suggestForm() {
  suggesting.value = true;
  notice.value = '正在调用百炼模型智能填入...';
  try {
    const suggestion = await fetchAssignmentSuggestion({
      mode: mode.value,
      current_title: form.title,
      assignment_type: form.assignment_type,
      user_id: form.user_id,
    });
    Object.assign(form, suggestion);
    notice.value = '智能填入已完成，可以继续微调后运行工作流。';
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error);
  } finally {
    suggesting.value = false;
  }
}
</script>
