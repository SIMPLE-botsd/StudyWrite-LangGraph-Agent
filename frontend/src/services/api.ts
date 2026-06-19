export interface WorkflowChunk {
  node: string;
  event: string;
  state: string;
  typy: string;
  text: string;
  message_id?: string;
}

export interface MemoryOverview {
  stats: {
    session_count: number;
    turn_count: number;
    memory_count_by_kind: Record<string, number>;
  };
  sessions: ConversationSession[];
  long_term_memories: LongTermMemory[];
}

export interface ConversationSession {
  session_id: string;
  user_id: string;
  title: string;
  feature: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  deleted: boolean;
  turn_count: number;
  last_user_message: string;
  last_assistant_message: string;
}

export interface ConversationTurn {
  session_id: string;
  turn_index: number;
  role: 'user' | 'assistant' | string;
  content: string;
  feature: string;
  metadata: Record<string, unknown>;
  nodes: Array<Record<string, unknown>>;
  created_at: string;
}

export interface SessionDetail {
  session: ConversationSession;
  turns: ConversationTurn[];
}

export interface LongTermMemory {
  id: string;
  kind: string;
  content: string;
  tags: string[];
  source_session_id: string;
  created_at: string;
  updated_at?: string;
  score?: number;
}

export interface ModelConfig {
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  allow_local_fallback: boolean;
  runtime: string;
}

export interface AssignmentSuggestion {
  title: string;
  assignment_type: string;
  task_description: string;
  materials: string;
  style: string;
  word_count: string;
  academic_level: string;
  rubric_focus: string;
  content: string;
  reference_text: string;
}

export interface RagflowStatus {
  base_url: string;
  has_api_key: boolean;
  default_dataset_count: number;
  default_top_k: number;
}

export interface RagflowDataset {
  id: string;
  name: string;
  description: string;
  document_count: number;
  chunk_count: number;
}

export interface RagflowChunk {
  content: string;
  score: number;
  document_name: string;
  dataset_id: string;
}

const API_PREFIX = '/writeapi/v1';

export async function streamWorkflow(
  endpoint: string,
  payload: Record<string, unknown>,
  onChunk: (chunk: WorkflowChunk) => void,
) {
  const response = await fetch(`${API_PREFIX}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, is_stream: true }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`请求失败：${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() || '';
    for (const frame of frames) {
      const line = frame
        .split('\n')
        .find((item) => item.startsWith('data:'));
      if (!line) continue;
      const raw = line.replace(/^data:\s*/, '').trim();
      if (!raw || raw === '{}') continue;
      onChunk(JSON.parse(raw));
    }
  }
}

export async function fetchMemoryOverview(userId: string): Promise<MemoryOverview> {
  const response = await fetch(`${API_PREFIX}/memory/overview?user_id=${encodeURIComponent(userId)}`);
  if (!response.ok) {
    throw new Error(`记忆读取失败：${response.status}`);
  }
  const json = await response.json();
  return json.data;
}

export async function fetchConversationSessions(payload: {
  userId: string;
  query?: string;
  includeDeleted?: boolean;
  limit?: number;
}): Promise<ConversationSession[]> {
  const params = new URLSearchParams({
    user_id: payload.userId,
    query: payload.query || '',
    include_deleted: String(Boolean(payload.includeDeleted)),
    limit: String(payload.limit || 30),
  });
  const response = await fetch(`${API_PREFIX}/memory/sessions?${params.toString()}`);
  const json = await readJsonOrThrow(response, '会话列表读取失败');
  return json.data || [];
}

export async function fetchConversationSession(userId: string, sessionId: string): Promise<SessionDetail> {
  const params = new URLSearchParams({ user_id: userId, include_deleted: 'true' });
  const response = await fetch(`${API_PREFIX}/memory/sessions/${encodeURIComponent(sessionId)}?${params.toString()}`);
  const json = await readJsonOrThrow(response, '会话详情读取失败');
  return json.data;
}

export async function softDeleteConversationSession(userId: string, sessionId: string) {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(`${API_PREFIX}/memory/sessions/${encodeURIComponent(sessionId)}?${params.toString()}`, {
    method: 'DELETE',
  });
  return readJsonOrThrow(response, '会话删除失败');
}

export async function restoreConversationSession(userId: string, sessionId: string) {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(`${API_PREFIX}/memory/sessions/${encodeURIComponent(sessionId)}/restore?${params.toString()}`, {
    method: 'POST',
  });
  return readJsonOrThrow(response, '会话恢复失败');
}

export async function searchMemory(payload: {
  userId: string;
  query: string;
  includeDeleted?: boolean;
  limit?: number;
}): Promise<{ sessions: ConversationSession[]; long_term_memories: LongTermMemory[] }> {
  const params = new URLSearchParams({
    user_id: payload.userId,
    query: payload.query,
    include_deleted: String(Boolean(payload.includeDeleted)),
    limit: String(payload.limit || 30),
  });
  const response = await fetch(`${API_PREFIX}/memory/search?${params.toString()}`);
  const json = await readJsonOrThrow(response, '记忆搜索失败');
  return json.data;
}

export async function createMemory(payload: {
  user_id: string;
  kind: string;
  content: string;
  tags: string[];
  source_session_id: string;
}) {
  const response = await fetch(`${API_PREFIX}/memory/long-term`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`记忆写入失败：${response.status}`);
  }
  return response.json();
}

export async function fetchModelConfig(): Promise<ModelConfig> {
  const response = await fetch(`${API_PREFIX}/model/config`);
  if (!response.ok) {
    throw new Error(`模型配置读取失败：${response.status}`);
  }
  const json = await response.json();
  return json.data;
}

export async function fetchAssignmentSuggestion(payload: {
  mode: string;
  current_title: string;
  assignment_type: string;
  user_id: string;
}): Promise<AssignmentSuggestion> {
  const response = await fetch(`${API_PREFIX}/assignment_suggestion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`智能填入失败：${response.status}`);
  }
  const json = await response.json();
  return json.data;
}

async function readJsonOrThrow(response: Response, fallback: string) {
  const json = await response.json().catch(() => null);
  if (!response.ok) {
    const message = json?.detail || json?.message || `${fallback}：${response.status}`;
    throw new Error(message);
  }
  return json;
}

export async function fetchRagflowStatus(): Promise<RagflowStatus> {
  const response = await fetch(`${API_PREFIX}/ragflow/status`);
  const json = await readJsonOrThrow(response, 'RAGFlow 状态读取失败');
  return json.data;
}

export async function fetchRagflowDatasets(): Promise<RagflowDataset[]> {
  const response = await fetch(`${API_PREFIX}/ragflow/datasets`);
  const json = await readJsonOrThrow(response, 'RAGFlow 知识库读取失败');
  return json.data || [];
}

export async function createRagflowDataset(payload: { name: string; description: string }): Promise<RagflowDataset> {
  const response = await fetch(`${API_PREFIX}/ragflow/datasets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const json = await readJsonOrThrow(response, 'RAGFlow 知识库创建失败');
  return json.data;
}

export async function initializeRagflowWritingDatasets() {
  const response = await fetch(`${API_PREFIX}/ragflow/initialize-writing`, {
    method: 'POST',
  });
  const json = await readJsonOrThrow(response, '写作知识库初始化失败');
  return json.data;
}

export async function uploadRagflowDocument(datasetId: string, file: File) {
  const form = new FormData();
  form.append('dataset_id', datasetId);
  form.append('file', file);
  const response = await fetch(`${API_PREFIX}/ragflow/documents`, {
    method: 'POST',
    body: form,
  });
  const json = await readJsonOrThrow(response, 'RAGFlow 文件上传失败');
  return json.data;
}

export async function retrieveRagflow(payload: {
  question: string;
  dataset_ids: string[];
  top_k: number;
}): Promise<{ chunks: RagflowChunk[]; raw_count: number; message?: string }> {
  const response = await fetch(`${API_PREFIX}/ragflow/retrieve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const json = await readJsonOrThrow(response, 'RAGFlow 检索失败');
  return json.data;
}
