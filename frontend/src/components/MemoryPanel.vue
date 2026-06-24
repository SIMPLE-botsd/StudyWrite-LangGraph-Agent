<template>
  <section class="panel memory-panel">
    <div class="panel-head compact">
      <div>
        <p class="eyebrow">Memory</p>
        <h2>会话与长记忆</h2>
      </div>
      <button class="icon-button soft" type="button" title="刷新" @click="refreshAll">
        <RefreshCw :size="17" />
      </button>
    </div>

    <div class="memory-stats">
      <div>
        <strong>{{ overview?.stats.session_count ?? 0 }}</strong>
        <span>会话</span>
      </div>
      <div>
        <strong>{{ overview?.stats.turn_count ?? 0 }}</strong>
        <span>消息</span>
      </div>
      <div>
        <strong>{{ totalMemories }}</strong>
        <span>记忆</span>
      </div>
    </div>

    <div class="memory-tabs">
      <button type="button" :class="{ active: activeTab === 'sessions' }" @click="activeTab = 'sessions'">
        <MessagesSquare :size="15" />
        <span>会话</span>
      </button>
      <button type="button" :class="{ active: activeTab === 'memories' }" @click="activeTab = 'memories'">
        <Brain :size="15" />
        <span>长期记忆</span>
      </button>
    </div>

    <div v-if="activeTab === 'sessions'" class="session-manager">
      <div class="session-search">
        <Search :size="15" />
        <input v-model="query" placeholder="搜索对话、题目、会话 ID" @keyup.enter="loadSessions" />
        <button type="button" @click="loadSessions">查找</button>
      </div>

      <label class="check-row deleted-toggle">
        <input v-model="includeDeleted" type="checkbox" @change="loadSessions" />
        <span>显示已删除会话</span>
      </label>

      <p v-if="message" class="hint-line" :class="{ error: isError }">{{ message }}</p>

      <div class="session-list">
        <article
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: selectedSession?.session.session_id === session.session_id, deleted: session.deleted }"
        >
          <button class="session-main" type="button" @click="openSession(session.session_id)">
            <span class="session-title">{{ session.title || '未命名会话' }}</span>
            <small>{{ featureName(session.feature) }} · {{ session.turn_count }} 条 · {{ formatTime(session.updated_at) }}</small>
            <p>{{ session.last_user_message || session.last_assistant_message || '暂无对话摘要' }}</p>
          </button>
          <button
            class="session-action"
            type="button"
            :title="session.deleted ? '恢复会话' : '软删除会话'"
            @click="session.deleted ? restoreSession(session.session_id) : deleteSession(session.session_id)"
          >
            <Undo2 v-if="session.deleted" :size="15" />
            <Trash2 v-else :size="15" />
          </button>
        </article>
      </div>

      <div v-if="selectedSession" class="session-detail">
        <div class="detail-head">
          <strong>{{ selectedSession.session.title || '会话详情' }}</strong>
          <small>{{ selectedSession.session.session_id }}</small>
        </div>
        <div class="turn-list">
          <article
            v-for="(turn, index) in selectedSession.turns"
            :key="`${turn.turn_index}-${turn.role}-${index}`"
            class="turn-item"
            :class="turn.role"
          >
            <span>{{ turn.role === 'user' ? '学生' : '智能体' }}</span>
            <p>{{ compact(turn.content, 520) }}</p>
          </article>
        </div>
      </div>
    </div>

    <div v-else class="long-memory-manager">
      <form class="memory-form" @submit.prevent="submit">
        <select v-model="kind">
          <option value="profile">画像</option>
          <option value="preference">偏好</option>
          <option value="rule">规则</option>
          <option value="experience">经验</option>
        </select>
        <input v-model="content" placeholder="手动添加一条长期记忆" />
        <button type="submit">写入</button>
      </form>

      <div class="memory-list">
        <article v-for="item in overview?.long_term_memories" :key="item.id" class="memory-item">
          <span class="memory-kind">{{ kindName(item.kind) }}</span>
          <p>{{ item.content }}</p>
          <small>{{ item.tags?.join(' / ') || '无标签' }}</small>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { Brain, MessagesSquare, RefreshCw, Search, Trash2, Undo2 } from 'lucide-vue-next';
import {
  fetchConversationSession,
  fetchConversationSessions,
  restoreConversationSession,
  softDeleteConversationSession,
  type ConversationSession,
  type MemoryOverview,
  type SessionDetail,
} from '../services/api';

const props = defineProps<{
  overview: MemoryOverview | null;
  userId: string;
}>();

const emit = defineEmits<{
  refresh: [];
  add: [payload: { kind: string; content: string }];
}>();

const activeTab = ref<'sessions' | 'memories'>('sessions');
const kind = ref('preference');
const content = ref('');
const query = ref('');
const includeDeleted = ref(false);
const sessions = ref<ConversationSession[]>([]);
const selectedSession = ref<SessionDetail | null>(null);
const message = ref('');
const isError = ref(false);

const totalMemories = computed(() => {
  const counts = props.overview?.stats.memory_count_by_kind || {};
  return Object.values(counts).reduce((sum, value) => sum + Number(value), 0);
});

watch(
  () => props.overview?.sessions,
  (value) => {
    if (!query.value.trim() && !includeDeleted.value) {
      sessions.value = [...(value || [])];
    }
  },
  { immediate: true },
);

onMounted(() => {
  loadSessions();
});

async function refreshAll() {
  emit('refresh');
  await loadSessions();
}

async function loadSessions() {
  try {
    sessions.value = await fetchConversationSessions({
      userId: props.userId,
      query: query.value,
      includeDeleted: includeDeleted.value,
      limit: 30,
    });
    message.value = sessions.value.length ? `找到 ${sessions.value.length} 个会话。` : '没有匹配的会话。';
    isError.value = false;
  } catch (error) {
    setError(error);
  }
}

async function openSession(sessionId: string) {
  try {
    selectedSession.value = await fetchConversationSession(props.userId, sessionId);
    message.value = '';
    isError.value = false;
  } catch (error) {
    setError(error);
  }
}

async function deleteSession(sessionId: string) {
  try {
    await softDeleteConversationSession(props.userId, sessionId);
    if (selectedSession.value?.session.session_id === sessionId) {
      selectedSession.value.session.deleted = true;
      selectedSession.value.session.deleted_at = new Date().toISOString();
    }
    emit('refresh');
    await loadSessions();
  } catch (error) {
    setError(error);
  }
}

async function restoreSession(sessionId: string) {
  try {
    await restoreConversationSession(props.userId, sessionId);
    emit('refresh');
    await loadSessions();
  } catch (error) {
    setError(error);
  }
}

function submit() {
  if (!content.value.trim()) return;
  emit('add', { kind: kind.value, content: content.value.trim() });
  content.value = '';
}

function kindName(value: string) {
  const map: Record<string, string> = {
    profile: '画像',
    preference: '偏好',
    rule: '规则',
    experience: '经验',
  };
  return map[value] || value;
}

function featureName(value: string) {
  const map: Record<string, string> = {
    generate_assignment: '生成文章',
    polish_assignment: '文章润色',
  };
  return map[value] || value || '写作';
}

function formatTime(value: string) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function compact(text: string, limit: number) {
  const clean = (text || '').replace(/\s+/g, ' ').trim();
  return clean.length > limit ? `${clean.slice(0, limit)}...` : clean;
}

function setError(error: unknown) {
  isError.value = true;
  message.value = error instanceof Error ? error.message : String(error);
}
</script>
