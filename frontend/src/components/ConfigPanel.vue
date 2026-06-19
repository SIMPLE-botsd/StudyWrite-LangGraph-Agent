<template>
  <section class="panel config-panel">
    <div class="panel-head compact">
      <div>
        <p class="eyebrow">Input</p>
        <h2>写作任务</h2>
      </div>
      <button class="icon-button soft" type="button" title="智能填入" :disabled="suggesting" @click="$emit('suggest')">
        <LoaderCircle v-if="suggesting" :size="17" class="spin" />
        <WandSparkles v-else :size="17" />
      </button>
    </div>

    <div class="form-grid">
      <label>
        <span>学生 ID</span>
        <input v-model="draft.user_id" />
      </label>

      <label>
        <span>会话 ID</span>
        <input v-model="draft.session_id" />
      </label>

      <label class="wide">
        <span>题目</span>
        <input v-model="draft.title" placeholder="例如：人工智能对大学学习方式的影响" />
      </label>

      <label>
        <span>任务类型</span>
        <select v-model="draft.assignment_type">
          <option>课程论文</option>
          <option>实验报告</option>
          <option>读书报告</option>
          <option>社会实践</option>
          <option>演讲稿</option>
          <option>润色修改</option>
          <option>仿写练习</option>
        </select>
      </label>

      <label>
        <span>目标字数</span>
        <input v-model="draft.word_count" />
      </label>

      <label class="wide">
        <span>表达风格</span>
        <input v-model="draft.style" />
      </label>

      <label class="wide">
        <span>评分关注点</span>
        <input v-model="draft.rubric_focus" />
      </label>

      <label class="wide">
        <span>{{ promptLabel }}</span>
        <textarea v-model="draft.task_description" rows="5" />
      </label>

      <label v-if="mode === 'polish'" class="wide">
        <span>原文</span>
        <textarea v-model="draft.content" rows="7" />
      </label>

      <label v-if="mode === 'imitate'" class="wide">
        <span>参考范文</span>
        <textarea v-model="draft.reference_text" rows="7" />
      </label>

      <label v-if="mode === 'draft'" class="wide">
        <span>材料 / 课堂笔记</span>
        <textarea v-model="draft.materials" rows="7" />
      </label>
    </div>

    <p v-if="notice" class="panel-notice">{{ notice }}</p>

    <KnowledgePanel
      v-model="draft"
      :title="draft.title"
      :task-description="draft.task_description"
      :materials="draft.materials"
    />

    <div class="toggle-box">
      <label class="check-row">
        <input v-model="draft.use_memory" type="checkbox" />
        <span>启用长期记忆</span>
      </label>
      <label class="check-row">
        <input v-model="draft.use_llm" type="checkbox" />
        <span>使用百炼云模型</span>
      </label>
    </div>

    <button class="primary-button" type="button" :disabled="running" @click="$emit('run')">
      <LoaderCircle v-if="running" :size="18" class="spin" />
      <Play v-else :size="18" />
      <span>{{ running ? '工作流运行中' : '运行工作流' }}</span>
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { LoaderCircle, Play, WandSparkles } from 'lucide-vue-next';
import KnowledgePanel from './KnowledgePanel.vue';

const props = defineProps<{
  modelValue: Record<string, any>;
  mode: string;
  running: boolean;
  suggesting: boolean;
  notice: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, any>];
  run: [];
  suggest: [];
}>();

const draft = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const promptLabel = computed(() => {
  if (props.mode === 'polish') return '润色要求';
  if (props.mode === 'imitate') return '新文章要求';
  return '作业要求';
});
</script>
