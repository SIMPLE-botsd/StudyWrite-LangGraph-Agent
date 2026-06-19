<template>
  <section class="knowledge-box">
    <div class="knowledge-title">
      <div>
        <p class="eyebrow">RAGFlow</p>
        <h3>知识检索</h3>
      </div>
      <span class="mini-status" :class="{ ok: status?.has_api_key }">
        {{ status?.has_api_key ? '已配置' : '未配置' }}
      </span>
    </div>

    <label class="check-row">
      <input v-model="draft.use_rag" type="checkbox" />
      <span>启用知识库引用</span>
    </label>

    <div class="knowledge-actions">
      <button class="tool-button" type="button" :disabled="loading" @click="loadDatasets">
        <RefreshCw :size="15" />
        <span>刷新</span>
      </button>
      <button class="tool-button" type="button" :disabled="loading" @click="initializeSeeds">
        <DatabaseZap :size="15" />
        <span>初始化写作库</span>
      </button>
    </div>

    <p v-if="!status?.has_api_key" class="hint-line">
      在 backend/.env 填写 RAGFLOW_API_KEY 后即可连接 cloud.ragflow.io。
    </p>

    <div v-if="datasets.length" class="dataset-list">
      <label
        v-for="dataset in datasets"
        :key="dataset.id"
        class="dataset-item"
      >
        <input
          type="checkbox"
          :checked="draft.rag_dataset_ids.includes(dataset.id)"
          @change="toggleDataset(dataset.id)"
        />
        <span>
          <strong>{{ dataset.name }}</strong>
          <small>{{ dataset.document_count || 0 }} 文档 · {{ dataset.chunk_count || 0 }} 片段</small>
        </span>
      </label>
    </div>
    <p v-else class="hint-line">还没有读取到知识库，先刷新或初始化写作库。</p>

    <label class="wide">
      <span>检索问题</span>
      <textarea
        v-model="draft.rag_query"
        rows="3"
        placeholder="为空时自动用题目、要求和材料检索"
      />
    </label>

    <div class="upload-row">
      <select v-model="uploadDatasetId">
        <option value="">选择上传知识库</option>
        <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
          {{ dataset.name }}
        </option>
      </select>
      <label class="file-button">
        <CloudUpload :size="15" />
        <span>上传</span>
        <input type="file" @change="handleUpload" />
      </label>
    </div>

    <button class="secondary-button" type="button" :disabled="loading || !draft.use_rag" @click="previewRetrieve">
      <Search :size="15" />
      <span>检索预览</span>
    </button>

    <p v-if="message" class="hint-line" :class="{ error: isError }">{{ message }}</p>

    <div v-if="previewChunks.length" class="rag-preview">
      <article v-for="(chunk, index) in previewChunks" :key="index">
        <strong>{{ chunk.document_name || `片段 ${index + 1}` }}</strong>
        <p>{{ chunk.content }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { CloudUpload, DatabaseZap, RefreshCw, Search } from 'lucide-vue-next';
import {
  fetchRagflowDatasets,
  fetchRagflowStatus,
  initializeRagflowWritingDatasets,
  retrieveRagflow,
  uploadRagflowDocument,
  type RagflowChunk,
  type RagflowDataset,
  type RagflowStatus,
} from '../services/api';

const props = defineProps<{
  modelValue: Record<string, any>;
  title: string;
  taskDescription: string;
  materials: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>];
}>();

const draft = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const status = ref<RagflowStatus | null>(null);
const datasets = ref<RagflowDataset[]>([]);
const previewChunks = ref<RagflowChunk[]>([]);
const loading = ref(false);
const message = ref('');
const isError = ref(false);
const uploadDatasetId = ref('');

onMounted(async () => {
  await refreshStatus();
  if (status.value?.has_api_key) {
    await loadDatasets();
  }
});

watch(datasets, () => {
  if (!uploadDatasetId.value && datasets.value.length) {
    uploadDatasetId.value = datasets.value[0].id;
  }
});

async function refreshStatus() {
  try {
    status.value = await fetchRagflowStatus();
  } catch (error) {
    setMessage(error, true);
  }
}

async function loadDatasets() {
  await withLoading(async () => {
    await refreshStatus();
    datasets.value = await fetchRagflowDatasets();
    message.value = datasets.value.length ? `已读取 ${datasets.value.length} 个知识库。` : 'RAGFlow 当前没有知识库。';
    isError.value = false;
  });
}

async function initializeSeeds() {
  await withLoading(async () => {
    await initializeRagflowWritingDatasets();
    datasets.value = await fetchRagflowDatasets();
    autoSelectWritingDatasets();
    message.value = '写作知识库已初始化并上传解析。';
    isError.value = false;
  });
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!uploadDatasetId.value) {
    setMessage('请先选择一个用于上传的知识库。', true);
    input.value = '';
    return;
  }
  await withLoading(async () => {
    await uploadRagflowDocument(uploadDatasetId.value, file);
    datasets.value = await fetchRagflowDatasets();
    message.value = `已上传 ${file.name}，RAGFlow 正在解析。`;
    isError.value = false;
  });
  input.value = '';
}

async function previewRetrieve() {
  const question = draft.value.rag_query || [props.title, props.taskDescription, props.materials]
    .filter(Boolean)
    .join('\n');
  if (!question.trim()) {
    setMessage('请先填写题目、要求或检索问题。', true);
    return;
  }
  await withLoading(async () => {
    const data = await retrieveRagflow({
      question,
      dataset_ids: draft.value.rag_dataset_ids,
      top_k: draft.value.rag_top_k || 6,
    });
    previewChunks.value = data.chunks || [];
    message.value = previewChunks.value.length ? `检索到 ${previewChunks.value.length} 个片段。` : (data.message || '没有检索到相关片段。');
    isError.value = false;
  });
}

function toggleDataset(datasetId: string) {
  const selected = new Set(draft.value.rag_dataset_ids || []);
  if (selected.has(datasetId)) {
    selected.delete(datasetId);
  } else {
    selected.add(datasetId);
  }
  draft.value.rag_dataset_ids = Array.from(selected);
}

function autoSelectWritingDatasets() {
  const writingIds = datasets.value
    .filter((dataset) => dataset.name.includes('写作') || dataset.name.includes('报告') || dataset.name.includes('AI'))
    .map((dataset) => dataset.id);
  draft.value.rag_dataset_ids = writingIds;
}

async function withLoading(task: () => Promise<void>) {
  loading.value = true;
  message.value = '正在连接 RAGFlow...';
  isError.value = false;
  try {
    await task();
  } catch (error) {
    setMessage(error, true);
  } finally {
    loading.value = false;
  }
}

function setMessage(error: unknown, failed: boolean) {
  isError.value = failed;
  message.value = error instanceof Error ? error.message : String(error);
}
</script>
