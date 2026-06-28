<template>
  <main class="chat-app-shell">
    <aside class="session-sidebar">
      <div class="app-brand">
        <div>
          <p class="eyebrow">DeepPen</p>
          <h1>写作智能体</h1>
        </div>
        <button class="icon-button" type="button" title="新建会话" @click="newSession">
          <Plus :size="18" />
        </button>
      </div>

      <div class="sidebar-search">
        <Search :size="16" />
        <input v-model="sessionQuery" placeholder="搜索会话" @keyup.enter="loadSessions" />
        <button type="button" @click="loadSessions">查找</button>
      </div>

      <div class="session-filter">
        <button type="button" :class="{ active: !showDeletedSessions }" @click="setDeletedView(false)">
          会话
        </button>
        <button type="button" :class="{ active: showDeletedSessions }" @click="setDeletedView(true)">
          回收站
        </button>
      </div>

      <div class="session-list chat-session-list">
        <article
          v-for="session in sessions"
          :key="session.session_id"
          class="chat-session-item"
          :class="{ active: selectedSessionId === session.session_id, deleted: session.deleted }"
          role="button"
          tabindex="0"
          @click="openSession(session.session_id)"
          @keydown.enter.prevent="openSession(session.session_id)"
          @keydown.space.prevent="openSession(session.session_id)"
        >
          <span>{{ session.title || '未命名会话' }}</span>
          <div class="session-item-foot">
            <small>{{ formatTime(session.updated_at) }}</small>
            <i v-if="session.deleted">已删除</i>
          </div>
          <button
            class="session-action-button"
            type="button"
            :title="session.deleted ? '恢复会话' : '删除会话'"
            @click.stop="session.deleted ? restoreSession(session.session_id) : deleteSession(session.session_id)"
          >
            <RotateCcw v-if="session.deleted" :size="14" />
            <Trash2 v-else :size="14" />
          </button>
        </article>
      </div>

      <div class="sidebar-footer">
        <ModelStatus :config="modelConfig" />
        <button class="secondary-button" type="button" :disabled="suggesting" @click="suggestForm">
          <LoaderCircle v-if="suggesting" :size="16" class="spin" />
          <Sparkles v-else :size="16" />
          <span>AI 生成题材</span>
        </button>
      </div>
    </aside>

    <section class="conversation-panel">
      <header class="conversation-header">
        <div>
          <p class="eyebrow">{{ featureName(modeFeature) }}</p>
          <h2>{{ conversationTitle }}</h2>
        </div>
        <div class="run-state" :class="{ running }">{{ running ? '运行中' : '就绪' }}</div>
      </header>

      <div ref="messagePanel" class="message-thread">
        <article
          v-for="message in chatMessages"
          :key="message.id"
          class="message-bubble"
          :class="message.role"
        >
          <div class="message-meta">
            <span class="message-author">
              <i>{{ message.role === 'user' ? '我' : 'D' }}</i>
              <b>{{ message.role === 'user' ? '用户' : 'DeepPen' }}</b>
            </span>
            <small>{{ message.time }}</small>
          </div>
          <div v-if="message.role === 'user' && userMessageCard(message)" class="user-message-card">
            <strong>{{ userMessageCard(message)?.title }}</strong>
            <div class="user-message-tags">
              <span v-for="tag in userMessageCard(message)?.tags" :key="tag">{{ tag }}</span>
            </div>
            <p v-if="userMessageCard(message)?.requirement">
              {{ userMessageCard(message)?.requirement }}
            </p>
            <div v-if="userMessageCard(message)?.materials" class="user-message-material">
              {{ userMessageCard(message)?.materials }}
            </div>
          </div>
          <p v-else-if="message.role === 'user'">{{ message.content }}</p>
          <p v-else>{{ message.content }}</p>
          <button
            v-if="message.articleContent"
            class="article-result-card"
            type="button"
            @click="loadArticleToEditor(message.articleContent, message.articleTitle)"
          >
            <FilePenLine :size="17" />
            <span>
              <b>写作结果</b>
              <strong>{{ message.articleTitle || '未命名文章' }}</strong>
            </span>
            <i>点击载入右侧编辑器</i>
          </button>
          <details v-if="message.nodes?.length" class="agent-log compact-agent-log">
            <summary class="agent-log-head">
              <BookOpen :size="16" />
              <span>Agent 执行过程</span>
              <i>已折叠，可展开查看</i>
            </summary>
            <div class="agent-log-body">
              <details
                v-for="event in message.nodes"
                :key="event.id"
                class="agent-event"
                :class="event.state"
              >
                <summary class="agent-event-summary">
                  <div class="agent-event-dot"></div>
                  <div>
                    <strong>{{ event.name }}</strong>
                    <p>{{ event.text }}</p>
                  </div>
                  <i>详情</i>
                </summary>
                <p class="agent-event-detail">{{ event.detail || nodeDetailText(event.node) }}</p>
              </details>
            </div>
          </details>
        </article>

        <article v-if="running && agentEvents.length" class="message-bubble assistant agent-bubble">
          <div class="message-meta">
            <span class="message-author">
              <i>D</i>
              <b>DeepPen</b>
            </span>
            <small>{{ running ? '运行中' : '已完成' }}</small>
          </div>
          <details class="agent-log">
            <summary class="agent-log-head">
              <BookOpen :size="16" />
              <span>Agent 执行过程</span>
              <i>{{ running ? '后台运行中，可展开查看' : '已折叠，可展开查看' }}</i>
            </summary>
            <div class="agent-log-body">
              <details
                v-for="event in agentEvents"
                :key="event.id"
                class="agent-event"
                :class="event.state"
              >
                <summary class="agent-event-summary">
                  <div class="agent-event-dot"></div>
                  <div>
                    <strong>{{ event.name }}</strong>
                    <p>{{ event.text }}</p>
                  </div>
                  <i>详情</i>
                </summary>
                <p class="agent-event-detail">{{ event.detail || nodeDetailText(event.node) }}</p>
              </details>
            </div>
          </details>
        </article>
      </div>

      <form class="composer" @submit.prevent="runWorkflow">
        <div class="composer-toolbar">
          <div class="segmented-control">
            <button
              v-for="item in modeOptions"
              :key="item.value"
              type="button"
              :class="{ active: mode === item.value }"
              @click="mode = item.value"
            >
              <component :is="item.icon" :size="16" />
              <span>{{ item.label }}</span>
            </button>
          </div>

          <label class="toolbar-field">
            <select v-model="assignmentTypeChoice" @change="syncChoiceFields">
              <option v-for="item in assignmentTypeOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <input
              v-if="assignmentTypeChoice === CUSTOM_OPTION"
              v-model="customAssignmentType"
              placeholder="输入自定义类型"
              @input="syncChoiceFields"
            />
          </label>

          <label class="toolbar-field">
            <select v-model="wordCountChoice" @change="syncChoiceFields">
              <option v-for="item in wordCountSelectOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <input
              v-if="wordCountChoice === CUSTOM_OPTION"
              v-model="customWordCount"
              placeholder="输入自定义字数"
              @input="syncChoiceFields"
            />
          </label>

          <label class="toolbar-field">
            <select v-model="styleChoice" @change="syncChoiceFields">
              <option v-for="item in styleSelectOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
            <input
              v-if="styleChoice === CUSTOM_OPTION"
              v-model="customStyle"
              placeholder="输入自定义风格"
              @input="syncChoiceFields"
            />
          </label>

          <label class="deep-polish-toggle" title="开启后会额外执行质量评估和深度修订，速度会慢一些。">
            <input v-model="form.deep_polish" type="checkbox" />
            <span>深度打磨</span>
          </label>

        </div>

        <div class="composer-fields">
          <label>
            <span>{{ titleLabel }}</span>
            <input v-model="form.title" :placeholder="titlePlaceholder" />
          </label>

          <label>
            <span>{{ primaryTextLabel }}</span>
            <textarea v-model="primaryTextModel" :placeholder="primaryTextPlaceholder" rows="4" />
          </label>

          <label>
            <span>{{ instructionLabel }}</span>
            <textarea v-model="form.task_description" :placeholder="instructionPlaceholder" rows="3" />
          </label>

        </div>

        <details class="tool-drawer">
          <summary>
            <BookOpen :size="16" />
            <span>知识库与记忆</span>
            <i>{{ form.use_rag ? selectedDatasetText : '未启用知识库' }}</i>
          </summary>

          <div class="tool-drawer-body">
            <label class="check-row">
              <input v-model="form.use_rag" type="checkbox" />
              <span>启用知识库引用</span>
            </label>

            <div class="knowledge-inline-actions">
              <button type="button" :disabled="ragLoading" @click="loadDatasets">
                <RefreshCw :size="15" />
                <span>刷新知识库</span>
              </button>
              <button type="button" :disabled="ragLoading" @click="initializeSeeds">
                <DatabaseZap :size="15" />
                <span>初始化写作库</span>
              </button>
            </div>

            <div v-if="datasets.length" class="dataset-chip-list">
              <button
                v-for="dataset in datasets"
                :key="dataset.id"
                type="button"
                :class="{ active: form.rag_dataset_ids.includes(dataset.id) }"
                @click="toggleDataset(dataset.id)"
              >
                {{ dataset.name }}
              </button>
            </div>

            <label>
              <span>检索问题</span>
              <textarea v-model="form.rag_query" rows="2" placeholder="为空时自动根据标题、要求和内容检索" />
            </label>

            <div class="rag-upload-row">
              <select v-model="uploadDatasetId">
                <option value="">{{ uploadTargetText }}</option>
                <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
                  {{ dataset.name }}
                </option>
              </select>
              <label class="file-button">
                <UploadCloud :size="15" />
                <span>上传资料</span>
                <input
                  type="file"
                  accept=".txt,.md,.markdown,.csv,.json,.log,.py,.js,.ts,.tsx,.vue,.html,.css"
                  @change="handleUpload"
                />
              </label>
              <button type="button" :disabled="ragLoading" @click="previewRetrieve">
                <Search :size="15" />
                <span>预览</span>
              </button>
            </div>

            <p v-if="ragMessage" class="hint-line" :class="{ error: ragError }">{{ ragMessage }}</p>

            <div v-if="ragPreviewChunks.length" class="rag-preview compact-preview">
              <article v-for="(chunk, index) in ragPreviewChunks" :key="index">
                <strong>{{ chunk.document_name || `片段 ${index + 1}` }}</strong>
                <p class="citation-highlight">{{ compact(chunk.content, 180) }}</p>
              </article>
            </div>

            <label class="check-row">
              <input v-model="form.use_memory" type="checkbox" />
              <span>启用长期记忆</span>
            </label>
          </div>
        </details>

        <div class="send-row">
          <p v-if="notice" class="composer-notice">{{ notice }}</p>
          <button class="send-button" type="submit" :disabled="running">
            <LoaderCircle v-if="running" :size="18" class="spin" />
            <Send v-else :size="18" />
            <span>{{ running ? '生成中' : '发送' }}</span>
          </button>
        </div>
      </form>
    </section>

    <aside class="editor-panel">
      <header class="editor-head">
        <div>
          <p class="eyebrow">正文</p>
          <h2>正文编辑器</h2>
        </div>
        <div class="editor-actions">
          <div class="editor-tabs">
            <button type="button" :class="{ active: editorMode === 'edit' }" @click="editorMode = 'edit'">编辑</button>
            <button type="button" :class="{ active: editorMode === 'preview' }" @click="editorMode = 'preview'">预览</button>
          </div>
          <button class="icon-button" type="button" title="复制干净文本（含脚注）" @click="copyResult">
            <Copy :size="17" />
          </button>
        </div>
      </header>
      <textarea
        v-if="editorMode === 'edit'"
        v-model="result"
        class="right-editor"
        placeholder="Agent 生成的 Markdown 正文会出现在这里，可以直接继续修改。"
      />
      <article v-else class="markdown-preview" v-html="renderedMarkdown"></article>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import {
  BookOpen,
  Copy,
  DatabaseZap,
  FilePenLine,
  LoaderCircle,
  Paintbrush,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Trash2,
  UploadCloud,
} from 'lucide-vue-next';
import ModelStatus from './components/ModelStatus.vue';
import {
  fetchAssignmentSuggestion,
  fetchConversationSession,
  fetchConversationSessions,
  fetchModelConfig,
  fetchRagflowDatasets,
  fetchRagflowStatus,
  initializeRagflowWritingDatasets,
  retrieveRagflow,
  restoreConversationSession,
  softDeleteConversationSession,
  streamWorkflow,
  uploadRagflowDocument,
  type ConversationSession,
  type ConversationTurn,
  type ModelConfig,
  type RagflowChunk,
  type RagflowDataset,
  type RagflowStatus,
  type WorkflowChunk,
} from './services/api';
import { markdownToHtml, markdownToPlainText } from './utils/markdown';
import { extractArticleTitle, isArticleContent, parsedUserMessage } from './utils/messages';
import { compact } from './utils/text';

type Mode = 'draft' | 'polish';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  nodes?: AgentEvent[];
  articleTitle?: string;
  articleContent?: string;
}

interface TraceNode {
  id: string;
  name: string;
  state: 'idle' | 'start' | 'done' | 'error';
  preview: string;
}

interface AgentEvent {
  id: string;
  node: string;
  name: string;
  state: 'start' | 'done' | 'error';
  text: string;
  detail?: string;
}

const mode = ref<Mode>('draft');
const running = ref(false);
const suggesting = ref(false);
const notice = ref('');
const result = ref('');
const runResult = ref('');
const editorMode = ref<'edit' | 'preview'>('preview');
const modelConfig = ref<ModelConfig | null>(null);
const sessions = ref<ConversationSession[]>([]);
const selectedSessionId = ref('');
const isDraftSession = ref(true);
const sessionQuery = ref('');
const showDeletedSessions = ref(false);
const chatMessages = ref<ChatMessage[]>([]);
const traceNodes = ref<TraceNode[]>([]);
const agentEvents = ref<AgentEvent[]>([]);
const streamingAssistantId = ref('');
const messagePanel = ref<HTMLElement | null>(null);
const CUSTOM_OPTION = '__custom__';
const assignmentTypeChoice = ref('课程论文');
const wordCountChoice = ref('1200');
const styleChoice = ref('清晰、正式、学生化');
const customAssignmentType = ref('');
const customWordCount = ref('');
const customStyle = ref('');

const ragStatus = ref<RagflowStatus | null>(null);
const datasets = ref<RagflowDataset[]>([]);
const ragPreviewChunks = ref<RagflowChunk[]>([]);
const ragLoading = ref(false);
const ragMessage = ref('');
const ragError = ref(false);
const uploadDatasetId = ref('');
const uploadedDocumentName = ref('');

const form = reactive<Record<string, any>>({
  user_id: 'student-demo',
  user_name: '学生',
  session_id: makeSessionId(),
  title: '人工智能对大学学习方式的影响',
  assignment_type: '课程论文',
  task_description: '结合课堂讨论和个人学习体验，分析生成式人工智能对大学生学习方式的影响，并提出合理使用建议。',
  materials: '课堂提到：AI 可以提升资料检索和初稿生成效率，但也可能造成依赖、误判资料可信度、削弱原创思考。',
  content: '人工智能现在很流行，很多同学都会用它写作业。它有好处也有坏处，所以我们要正确看待。',
  style: '清晰、正式、学生化',
  word_count: '1200',
  academic_level: '本科课程作业',
  rubric_focus: '观点明确，论证有材料支撑，体现个人反思，避免直接照搬 AI 输出。',
  use_memory: true,
  use_llm: true,
  memory_k: 5,
  use_rag: false,
  rag_dataset_ids: [],
  rag_query: '',
  rag_top_k: 6,
  deep_polish: false,
});

const modeOptions = [
  { value: 'draft', label: '生成文章', icon: FilePenLine },
  { value: 'polish', label: '文章润色', icon: Paintbrush },
] as const;

const assignmentTypeOptions = [
  { value: '课程论文', label: '课程论文' },
  { value: '实验报告', label: '实验报告' },
  { value: '读书报告', label: '读书报告' },
  { value: '社会实践', label: '社会实践' },
  { value: '演讲稿', label: '演讲稿' },
  { value: '润色修改', label: '润色修改' },
  { value: CUSTOM_OPTION, label: '自定义' },
];
const wordCountSelectOptions = [
  { value: '600', label: '600 字' },
  { value: '800', label: '800 字' },
  { value: '1000', label: '1000 字' },
  { value: '1200', label: '1200 字' },
  { value: '1500', label: '1500 字' },
  { value: '2000', label: '2000 字' },
  { value: CUSTOM_OPTION, label: '自定义' },
];
const styleSelectOptions = [
  { value: '清晰、正式、学生化', label: '清晰、正式、学生化' },
  { value: '自然、严谨、学生化', label: '自然、严谨、学生化' },
  { value: '学术、规范、有逻辑', label: '学术、规范、有逻辑' },
  { value: '简洁、直接、少套话', label: '简洁、直接、少套话' },
  { value: '表达流畅、适合答辩', label: '表达流畅、适合答辩' },
  { value: CUSTOM_OPTION, label: '自定义' },
];

const traceLabels: Record<string, string> = {
  recall_memory: '读取记忆',
  analyze_assignment: '理解要求',
  retrieve_knowledge: '匹配知识',
  plan_outline: '规划提纲',
  write_draft: '生成正文',
  evaluate_draft: '质量评估',
  revise_draft: '深度修订',
  render: '整理结果',
  save_memory: '写入记忆',
};

const fallbackHistoryNodeSteps: Array<[string, string, string, string]> = [
  ['recall_memory', '读取记忆', '旧记录缺少节点输出', '旧会话没有保存该节点传给下一步的真实内容，请重新生成一次查看完整节点输出。'],
  ['analyze_assignment', '理解要求', '旧记录缺少节点输出', '旧会话没有保存任务分析节点的真实输出。新会话会显示 brief 字段内容。'],
  ['retrieve_knowledge', '匹配知识', '旧记录缺少节点输出', '旧会话没有保存知识匹配节点的真实输出。新会话会显示 knowledge_context 字段内容。'],
  ['plan_outline', '规划提纲', '旧记录缺少节点输出', '旧会话没有保存提纲节点的真实输出。新会话会显示 outline 字段内容。'],
  ['write_draft', '生成正文', '旧记录缺少节点输出', '旧会话没有保存正文生成节点的真实输出。新会话会显示 draft 字段内容。'],
  ['render', '整理结果', '旧记录缺少节点输出', '旧会话没有保存整理节点的真实输出。右侧编辑器中仍保留最终正文。'],
  ['save_memory', '写入记忆', '旧记录缺少节点输出', '旧会话没有保存记忆写入节点的真实输出。新会话会显示 memory_writeback 字段内容。'],
];

const modeFeature = computed(() => {
  if (mode.value === 'polish') return 'polish_assignment';
  return 'generate_assignment';
});

const conversationTitle = computed(() => form.title || '新的写作会话');

const renderedMarkdown = computed(() => markdownToHtml(result.value || ''));

const titleLabel = computed(() => {
  if (mode.value === 'polish') return '文章标题';
  return '标题';
});

const titlePlaceholder = computed(() => {
  return '例如：人工智能对大学学习方式的影响';
});

const primaryTextLabel = computed(() => {
  if (mode.value === 'polish') return '原文内容';
  return '内容 / 资料';
});

const primaryTextPlaceholder = computed(() => {
  if (mode.value === 'polish') return '粘贴需要润色的文章原文';
  return '填写课堂材料、写作素材、你的观点或老师给的资料';
});

const instructionLabel = computed(() => {
  if (mode.value === 'polish') return '润色要求';
  return '写作要求';
});

const instructionPlaceholder = computed(() => {
  if (mode.value === 'polish') return '例如：保留原意，增强逻辑和学术表达';
  return '例如：结合课程讨论分析影响，并提出合理使用建议';
});

const primaryTextModel = computed({
  get() {
    if (mode.value === 'polish') return form.content;
    return form.materials;
  },
  set(value: string) {
    if (mode.value === 'polish') {
      form.content = value;
    } else {
      form.materials = value;
    }
  },
});

const selectedDatasetText = computed(() => {
  const names = selectedDatasetNames.value;
  if (uploadedDocumentName.value) return uploadedDocumentName.value;
  if (!names.length) return '未选择资料';
  return compact(names.join('、'), 36);
});

const selectedDatasetNames = computed(() => {
  const selected = new Set(form.rag_dataset_ids || []);
  const names = datasets.value
    .filter((dataset) => selected.has(dataset.id))
    .map((dataset) => dataset.name)
    .filter(Boolean);
  if (uploadedDocumentName.value && !names.includes(uploadedDocumentName.value)) {
    names.unshift(uploadedDocumentName.value);
  }
  return names;
});

const uploadTargetText = computed(() => uploadedDocumentName.value || '上传后显示文件名');

const LAST_SESSION_KEY = 'deeppen:lastSessionId';

watch(mode, (value) => {
  if (value === 'polish') {
    form.assignment_type = '润色修改';
  } else if (!['课程论文', '实验报告', '读书报告', '社会实践', '演讲稿'].includes(form.assignment_type)) {
    form.assignment_type = '课程论文';
  }
  syncChoicesFromForm();
});

watch(() => form.title, () => {
  if (isDraftSession.value) return;
  const target = sessions.value.find((item) => item.session_id === form.session_id);
  if (target && target.turn_count === 0) {
    target.title = form.title?.trim() || '新的写作会话';
    target.updated_at = new Date().toISOString();
  }
});

onMounted(async () => {
  syncChoicesFromForm();
  resetMessages();
  await Promise.all([loadSessions(), refreshModelConfig(), refreshRagStatus()]);
  await openInitialSession();
  if (ragStatus.value?.has_api_key || ragStatus.value?.backend === 'turbovec') {
    await loadDatasets();
  }
});

function makeSessionId() {
  return `deeppen-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowText() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function syncChoiceFields() {
  form.assignment_type = assignmentTypeChoice.value === CUSTOM_OPTION
    ? (customAssignmentType.value.trim() || '自定义类型')
    : assignmentTypeChoice.value;
  form.word_count = wordCountChoice.value === CUSTOM_OPTION
    ? (customWordCount.value.trim() || '自定义字数')
    : wordCountChoice.value;
  form.style = styleChoice.value === CUSTOM_OPTION
    ? (customStyle.value.trim() || '自定义风格')
    : styleChoice.value;
}

function syncChoicesFromForm() {
  const assignmentValues = assignmentTypeOptions.map((item) => item.value);
  const wordValues = wordCountSelectOptions.map((item) => item.value);
  const styleValues = styleSelectOptions.map((item) => item.value);

  if (assignmentValues.includes(form.assignment_type)) {
    assignmentTypeChoice.value = form.assignment_type;
  } else {
    assignmentTypeChoice.value = CUSTOM_OPTION;
    customAssignmentType.value = form.assignment_type || '';
  }

  if (wordValues.includes(form.word_count)) {
    wordCountChoice.value = form.word_count;
  } else {
    wordCountChoice.value = CUSTOM_OPTION;
    customWordCount.value = form.word_count || '';
  }

  if (styleValues.includes(form.style)) {
    styleChoice.value = form.style;
  } else {
    styleChoice.value = CUSTOM_OPTION;
    customStyle.value = form.style || '';
  }
}

function resetMessages() {
  chatMessages.value = [{
    id: `welcome-${Date.now()}`,
    role: 'assistant',
    content: '你好，我是 DeepPen。选择生成文章或文章润色后，把标题、内容和要求发给我；需要更细的质量评估与修订时，可以打开“深度打磨”。',
    time: nowText(),
  }];
}

async function openInitialSession() {
  if (sessionQuery.value || showDeletedSessions.value || !sessions.value.length) {
    startDraftSession(false);
    return;
  }

  const lastSessionId = localStorage.getItem(LAST_SESSION_KEY) || '';
  const target = sessions.value.find((item) => item.session_id === lastSessionId) || sessions.value[0];
  if (target?.session_id) {
    await openSession(target.session_id, { silentError: true });
  } else {
    startDraftSession(false);
  }
}

function newSession() {
  startDraftSession(true);
}

function startDraftSession(showTip: boolean) {
  form.session_id = makeSessionId();
  selectedSessionId.value = '';
  isDraftSession.value = true;
  showDeletedSessions.value = false;
  sessionQuery.value = '';
  result.value = '';
  traceNodes.value = [];
  agentEvents.value = [];
  streamingAssistantId.value = '';
  uploadedDocumentName.value = '';
  notice.value = showTip ? '已进入新会话草稿，发送后会自动保存到左侧列表。' : '';
  resetMessages();
}

async function loadSessions() {
  sessions.value = await fetchConversationSessions({
    userId: form.user_id,
    query: sessionQuery.value,
    includeDeleted: showDeletedSessions.value,
    deletedOnly: showDeletedSessions.value,
    limit: 40,
  });
}

async function setDeletedView(value: boolean) {
  showDeletedSessions.value = value;
  await loadSessions();
  if (value) {
    selectedSessionId.value = '';
    return;
  }
  const selectedStillVisible = sessions.value.some((item) => item.session_id === selectedSessionId.value);
  if (!isDraftSession.value && selectedStillVisible) return;
  await openInitialSession();
}

async function openSession(sessionId: string, options: { silentError?: boolean } = {}) {
  running.value = false;
  streamingAssistantId.value = '';
  uploadedDocumentName.value = '';
  selectedSessionId.value = sessionId;
  isDraftSession.value = false;
  form.session_id = sessionId;
  let detail;
  try {
    detail = await fetchConversationSession(form.user_id, sessionId);
  } catch (error) {
    if (!options.silentError) {
      notice.value = error instanceof Error ? error.message : String(error);
    }
    startDraftSession(false);
    return;
  }
  form.title = detail.session.title || form.title;
  const lastUser = [...detail.turns].reverse().find((turn) => turn.role === 'user');
  if (lastUser?.content) {
    hydrateFormFromUserMessage(lastUser.content);
  }
  syncChoicesFromForm();
  chatMessages.value = detail.turns.map((turn: ConversationTurn, index: number) => {
    const articleContent = turn.role === 'assistant' && isArticleTurn(turn) ? turn.content : undefined;
    const nextTurn = detail.turns[index + 1];
    return {
      id: `${turn.role}-${turn.turn_index}-${index}`,
      role: turn.role === 'user' ? 'user' : 'assistant',
      content: turn.role === 'user' ? historyUserContent(turn, nextTurn) : displayTurnContent(turn),
      time: formatTime(turn.created_at),
      articleTitle: articleContent ? articleTitleFromTurn(turn) : undefined,
      articleContent,
      nodes: turn.role === 'assistant' ? historyNodesFromTurn(turn) : undefined,
    };
  });
  if (!chatMessages.value.length) {
    chatMessages.value = [{
      id: `empty-${sessionId}`,
      role: 'assistant',
      content: '这个会话暂时还没有写作记录，可以继续在下方发送新任务。',
      time: nowText(),
    }];
  }
  const lastAssistantArticle = [...detail.turns]
    .reverse()
    .find((turn) => turn.role === 'assistant' && isArticleTurn(turn));
  result.value = lastAssistantArticle?.content || '';
  traceNodes.value = [];
  agentEvents.value = [];
  if (!detail.session.deleted) {
    localStorage.setItem(LAST_SESSION_KEY, sessionId);
  }
  await scrollMessages();
}

async function deleteSession(sessionId: string) {
  try {
    await softDeleteConversationSession(form.user_id, sessionId);
    if (localStorage.getItem(LAST_SESSION_KEY) === sessionId) {
      localStorage.removeItem(LAST_SESSION_KEY);
    }
    showDeletedSessions.value = false;
    await loadSessions();
    if (selectedSessionId.value === sessionId) {
      await openInitialSession();
    }
    notice.value = '会话已移入回收站。';
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error);
  }
}

async function restoreSession(sessionId: string) {
  try {
    await restoreConversationSession(form.user_id, sessionId);
    showDeletedSessions.value = false;
    await loadSessions();
    await openSession(sessionId);
    notice.value = '会话已恢复。';
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error);
  }
}

async function refreshModelConfig() {
  modelConfig.value = await fetchModelConfig();
}

async function refreshRagStatus() {
  try {
    ragStatus.value = await fetchRagflowStatus();
  } catch (error) {
    setRagMessage(error, true);
  }
}

async function suggestForm() {
  suggesting.value = true;
  notice.value = '正在调用模型生成新的写作题材...';
  try {
    const suggestion = await fetchAssignmentSuggestion({
      mode: mode.value,
      current_title: '',
      assignment_type: form.assignment_type,
      user_id: form.user_id,
    });
    Object.assign(form, suggestion);
    syncChoicesFromForm();
    notice.value = 'AI 题材已生成，可以继续微调后发送。';
    await refreshModelConfig();
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error);
  } finally {
    suggesting.value = false;
  }
}

async function runWorkflow() {
  syncChoiceFields();
  const validation = validateForm();
  if (validation) {
    notice.value = validation;
    return;
  }

  running.value = true;
  notice.value = 'Agent 工作流正在运行...';
  runResult.value = '';
  traceNodes.value = [];
  agentEvents.value = [];
  selectedSessionId.value = form.session_id;

  chatMessages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    content: buildUserMessage(),
    time: nowText(),
  });
  streamingAssistantId.value = `assistant-${Date.now()}`;
  chatMessages.value.push({
    id: streamingAssistantId.value,
    role: 'assistant',
    content: '已收到，DeepPen 正在后台写作。完整正文会输出到右侧文本编辑器；需要时可以展开查看执行过程。',
    time: nowText(),
  });
  await scrollMessages();

  const endpoint = mode.value === 'polish'
    ? '/polish_writer'
    : '/student_writer';

  try {
    await streamWorkflow(endpoint, buildPayload(), handleChunk);
    if (runResult.value) {
      updateStreamingAssistant('已完成，正文已写入右侧文本编辑器。你可以直接继续修改。');
      attachNodesToStreamingAssistant();
      attachArticleToStreamingAssistant(runResult.value);
      agentEvents.value = [];
    }
    await refreshModelConfig();
    await loadSessions();
    isDraftSession.value = false;
    selectedSessionId.value = form.session_id;
    localStorage.setItem(LAST_SESSION_KEY, form.session_id);
    notice.value = '工作流已完成。';
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    updateStreamingAssistant(`执行失败：${message}`);
    notice.value = message;
  } finally {
    running.value = false;
    streamingAssistantId.value = '';
    await scrollMessages();
  }
}

function validateForm() {
  if (!form.title.trim()) return '请先填写标题。';
  if (mode.value === 'polish' && !form.content.trim()) return '请粘贴需要润色的原文。';
  if (!form.task_description.trim()) return '请填写写作要求。';
  return '';
}

function hydrateFormFromUserMessage(content: string) {
  const lines = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return;

  const readField = (label: string) => {
    const prefix = `${label}：`;
    const hit = lines.find((line) => line.startsWith(prefix));
    return hit ? hit.slice(prefix.length).trim() : '';
  };

  const labeledTitle = readField('标题');
  const labeledFeature = readField('功能');
  const labeledType = readField('类型');
  const labeledWordCount = readField('字数');
  const labeledDeepPolish = readField('深度打磨');
  const labeledRequirement = readField('要求');
  const labeledMaterials = readField('内容/资料');
  const labeledOriginal = readField('原文');
  const labeledKnowledge = readField('知识库');

  if (labeledFeature.includes('润色')) mode.value = 'polish';
  if (labeledFeature.includes('生成')) mode.value = 'draft';
  if (labeledTitle) form.title = labeledTitle;
  if (labeledType) form.assignment_type = labeledType;
  if (labeledWordCount) form.word_count = labeledWordCount;
  if (labeledDeepPolish) form.deep_polish = labeledDeepPolish.includes('开启');
  if (labeledRequirement) form.task_description = labeledRequirement;
  if (labeledMaterials) form.materials = labeledMaterials;
  if (labeledOriginal) form.content = labeledOriginal;
  if (labeledKnowledge) form.use_rag = true;

  if (labeledTitle || labeledRequirement || labeledMaterials || labeledOriginal) return;

  form.title = lines[0] || form.title;
  if (lines[1]) form.assignment_type = lines[1];
  if (lines[2]) form.task_description = lines[2];
  if (lines.length > 3) form.materials = lines.slice(3).join('\n');
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
    rag_dataset_names: selectedDatasetNames.value,
    rag_query: form.rag_query,
    rag_top_k: form.rag_top_k,
    deep_polish: form.deep_polish,
  };

  if (mode.value === 'polish') {
    return {
      ...base,
      content: form.content,
      change_request: form.task_description,
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

function buildUserMessage() {
  const lines = [
    `功能：${featureName(modeFeature.value)}`,
    `标题：${form.title}`,
    `类型：${form.assignment_type}`,
    `字数：${form.word_count}`,
    `深度打磨：${form.deep_polish ? '开启' : '关闭'}`,
    `要求：${form.task_description}`,
  ];
  if (mode.value === 'polish') {
    lines.push(`原文：${form.content}`);
  } else {
    lines.push(`内容/资料：${form.materials}`);
  }
  if (form.use_rag) lines.push(`知识库：${selectedDatasetText.value}`);
  return lines.join('\n');
}

function handleChunk(chunk: WorkflowChunk) {
  const existing = traceNodes.value.find((item) => item.id === chunk.node);
  const nextState = chunk.event === 'error' ? 'error' : chunk.event === 'start' ? 'start' : 'done';
  const preview = compact(chunk.text || '', 160);

  if (existing) {
    existing.state = nextState;
    existing.preview = preview;
  } else if (traceLabels[chunk.node]) {
    traceNodes.value.push({
      id: chunk.node,
      name: traceLabels[chunk.node],
      state: nextState,
      preview,
    });
  }

  if (traceLabels[chunk.node] && chunk.node !== 'render') {
    pushAgentEvent(chunk, nextState, preview);
  }

  if (chunk.node === 'render' && chunk.typy === 'result') {
    runResult.value = chunk.text;
    result.value = chunk.text;
    updateStreamingAssistant('正文已生成，并同步到右侧文本编辑器。');
  }
  if (chunk.event === 'error') {
    updateStreamingAssistant(chunk.text);
  }
  scrollMessages();
}

function pushAgentEvent(chunk: WorkflowChunk, state: AgentEvent['state'], preview: string) {
  const text = state === 'start'
    ? `开始执行：${traceLabels[chunk.node]}`
    : nodeEventText(chunk.node, state, preview);
  const detail = state === 'start'
    ? '节点已开始执行，等待后端返回该节点传给下一步的输出。'
    : nodeOutputDetail(chunk.node, chunk.text);
  agentEvents.value.push({
    id: `${chunk.node}-${chunk.event}-${agentEvents.value.length}-${Date.now()}`,
    node: chunk.node,
    name: traceLabels[chunk.node],
    state,
    text,
    detail,
  });
}

function nodeEventText(node: string, state: AgentEvent['state'], preview: string) {
  if (state === 'error') return preview || `${traceLabels[node]}执行失败`;
  const quietNodes = new Set(['recall_memory', 'analyze_assignment', 'retrieve_knowledge', 'plan_outline', 'save_memory']);
  if (quietNodes.has(node)) return `${traceLabels[node]}已完成`;
  if (node === 'write_draft') return '完整正文已生成';
  if (node === 'evaluate_draft') return '质量评估已完成';
  if (node === 'revise_draft') return '深度修订已完成';
  return preview || `${traceLabels[node]}已完成`;
}

function nodeDetailText(node: string) {
  return `旧记录没有保存“${traceLabels[node] || node}”节点的真实输出。请重新生成一次，新会话会保存该节点传给下一步的完整内容。`;
}

function nodeOutputDetail(node: string, output: string) {
  const clean = (output || '').trim();
  if (!clean) return nodeDetailText(node);
  if (node === 'render') {
    return `该节点输出完整 Markdown 正文，已同步到右侧编辑器。正文长度 ${clean.length} 字符。`;
  }
  return clean;
}

function updateStreamingAssistant(content: string) {
  const target = chatMessages.value.find((item) => item.id === streamingAssistantId.value);
  if (target) {
    target.content = content;
    target.time = nowText();
  }
}

function attachArticleToStreamingAssistant(content: string) {
  if (!isArticleContent(content)) return;
  const target = chatMessages.value.find((item) => item.id === streamingAssistantId.value);
  if (target) {
    target.articleContent = content;
    target.articleTitle = extractArticleTitle(content) || form.title || '未命名文章';
  }
}

function attachNodesToStreamingAssistant() {
  const target = chatMessages.value.find((item) => item.id === streamingAssistantId.value);
  if (!target || !agentEvents.value.length) return;
  target.nodes = agentEvents.value.map((event, index) => ({
    ...event,
    id: `${event.node}-snapshot-${index}`,
  }));
}

function loadArticleToEditor(content?: string, title?: string) {
  if (!content?.trim()) return;
  result.value = content;
  editorMode.value = 'preview';
  if (title) {
    notice.value = `已载入《${title}》。`;
  }
}

async function loadDatasets() {
  await withRagLoading(async () => {
    await refreshRagStatus();
    datasets.value = await fetchRagflowDatasets();
    ragMessage.value = datasets.value.length ? `已读取 ${datasets.value.length} 个知识库。` : '当前没有可用知识库。';
    ragError.value = false;
  });
}

async function initializeSeeds() {
  await withRagLoading(async () => {
    await initializeRagflowWritingDatasets();
    datasets.value = await fetchRagflowDatasets();
    form.rag_dataset_ids = datasets.value
      .filter((dataset) => dataset.name.includes('写作') || dataset.name.includes('报告') || dataset.name.includes('AI'))
      .map((dataset) => dataset.id);
    ragMessage.value = '写作知识库已初始化。';
    ragError.value = false;
  });
}

function toggleDataset(datasetId: string) {
  const selected = new Set(form.rag_dataset_ids || []);
  if (selected.has(datasetId)) {
    selected.delete(datasetId);
  } else {
    selected.add(datasetId);
  }
  form.rag_dataset_ids = Array.from(selected);
}

async function previewRetrieve() {
  const question = form.rag_query || [form.title, form.task_description, primaryTextModel.value]
    .filter(Boolean)
    .join('\n');
  if (!question.trim()) {
    setRagMessage('请先填写标题、要求或检索问题。', true);
    return;
  }
  await withRagLoading(async () => {
    const data = await retrieveRagflow({
      question,
      dataset_ids: form.rag_dataset_ids,
      top_k: form.rag_top_k || 6,
    });
    ragPreviewChunks.value = data.chunks || [];
    ragMessage.value = ragPreviewChunks.value.length ? `检索到 ${ragPreviewChunks.value.length} 个片段。` : (data.message || '没有检索到相关片段。');
    ragError.value = false;
  });
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  await withRagLoading(async () => {
    const uploadResult = await uploadRagflowDocument(uploadDatasetId.value, file);
    datasets.value = await fetchRagflowDatasets();
    uploadedDocumentName.value = file.name;
    const documentDatasetId = uploadResult?.documents?.[0]?.dataset_id || uploadDatasetId.value;
    if (documentDatasetId && !form.rag_dataset_ids.includes(documentDatasetId)) {
      form.rag_dataset_ids = [...form.rag_dataset_ids, documentDatasetId];
    }
    form.use_rag = true;
    ragMessage.value = `已上传 ${file.name}，后续写作会优先引用这份资料。`;
    ragError.value = false;
  });
  input.value = '';
}

async function withRagLoading(task: () => Promise<void>) {
  ragLoading.value = true;
  ragMessage.value = '正在连接知识库...';
  ragError.value = false;
  try {
    await task();
  } catch (error) {
    setRagMessage(error, true);
  } finally {
    ragLoading.value = false;
  }
}

function setRagMessage(error: unknown, failed: boolean) {
  ragError.value = failed;
  ragMessage.value = error instanceof Error ? error.message : String(error);
}

async function copyResult() {
  if (!result.value.trim()) {
    notice.value = '右侧还没有可复制的正文。';
    return;
  }
  const text = markdownToPlainText(result.value);
  await navigator.clipboard.writeText(text);
  notice.value = '已复制干净文本，包含脚注引用内容。';
}

async function scrollMessages() {
  await nextTick();
  if (messagePanel.value) {
    messagePanel.value.scrollTop = messagePanel.value.scrollHeight;
  }
}

function featureName(value: string) {
  const map: Record<string, string> = {
    generate_assignment: '生成文章',
    polish_assignment: '文章润色',
  };
  return map[value] || value || '写作';
}

function formatTime(value: string) {
  if (!value) return nowText();
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function displayTurnContent(turn: ConversationTurn) {
  if (turn.role === 'assistant') {
    if (isArticleTurn(turn)) {
      return '该轮写作结果已保存，可点击下方标题重新载入右侧编辑器。';
    }
    return compact(turn.content || '该轮没有生成可载入编辑器的正文。', 220);
  }
  return turn.content;
}

function historyUserContent(turn: ConversationTurn, nextTurn?: ConversationTurn) {
  const content = turn.content || '';
  if (/^知识库：/m.test(content)) return content;
  const sources = citationSourcesFromMarkdown(nextTurn?.content || '');
  if (!sources.length) return content;
  return `${content}\n知识库：${compact(sources.join('、'), 42)}`;
}

function citationSourcesFromMarkdown(markdown: string) {
  const sources = new Set<string>();
  for (const match of markdown.matchAll(/^\[\^\d+\]:\s*([^\n·]+)/gm)) {
    const source = match[1]?.trim();
    if (source) sources.add(source);
  }
  return Array.from(sources);
}

function userMessageCard(message: ChatMessage) {
  if (message.role !== 'user') return null;
  return parsedUserMessage(message.content);
}

function articleTitleFromTurn(turn: ConversationTurn) {
  return extractArticleTitle(turn.content) || '未命名文章';
}

function isArticleTurn(turn: ConversationTurn) {
  return turn.role === 'assistant' && isArticleContent(turn.content);
}

function historyNodesFromTurn(turn: ConversationTurn): AgentEvent[] {
  const nodes = Array.isArray(turn.nodes) ? turn.nodes : [];
  const parsed = nodes
    .map((item, index) => normalizeHistoryNode(item, index))
    .filter((item): item is AgentEvent => Boolean(item));
  if (parsed.length) return parsed;
  return turn.content ? fallbackHistoryNodesFromTurn(turn) : [];
}

function fallbackHistoryNodesFromTurn(turn: ConversationTurn): AgentEvent[] {
  const steps = [...fallbackHistoryNodeSteps];
  const scores = turn.metadata && typeof turn.metadata === 'object'
    ? (turn.metadata as Record<string, unknown>).scores
    : null;
  const hasDeepPolish = Boolean(
    turn.content.includes('## 深度打磨记录')
    || (scores && typeof scores === 'object' && Object.keys(scores as Record<string, unknown>).length),
  );
  if (hasDeepPolish) {
    steps.splice(
      5,
      0,
      ['evaluate_draft', '质量评估', '旧记录缺少节点输出', '旧会话没有保存质量评估节点的真实输出。新会话会显示 critique 字段内容。'],
      ['revise_draft', '深度修订', '旧记录缺少节点输出', '旧会话没有保存修订节点的真实输出。新会话会显示修订后的 draft 字段内容。'],
    );
  }
  return steps.map(([node, name, text, detail], index) => ({
    id: `${node}-${index}`,
    node,
    name,
    state: 'done',
    text,
    detail,
  }));
}

function normalizeHistoryNode(item: Record<string, unknown>, index: number): AgentEvent | null {
  if (!item || typeof item !== 'object') return null;
  const node = String(item.node || item.id || `history-node-${index}`);
  const name = String(item.name || traceLabels[node] || `节点 ${index + 1}`);
  const rawState = String(item.state || 'done');
  const state: AgentEvent['state'] = rawState === 'start' || rawState === 'error' ? rawState : 'done';
  const text = compact(String(item.text || item.preview || `${name}已完成`), 160);
  const detail = String(item.detail || nodeDetailText(node));
  return {
    id: `${node}-${index}`,
    node,
    name,
    state,
    text,
    detail,
  };
}

</script>
