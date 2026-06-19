<template>
  <section class="panel trace-panel">
    <div class="panel-head compact">
      <div>
        <p class="eyebrow">Graph</p>
        <h2>执行流程</h2>
      </div>
      <div class="status-pill" :class="{ running }">{{ running ? '运行中' : '待命' }}</div>
    </div>

    <div class="trace-list">
      <article
        v-for="node in visibleNodes"
        :key="node.id"
        class="trace-item"
        :class="node.state"
      >
        <div class="trace-index">{{ node.index }}</div>
        <div class="trace-copy">
          <h3>{{ node.name }}</h3>
          <p>{{ node.preview || '等待节点输出' }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

export interface TraceNode {
  id: string;
  name: string;
  state: 'idle' | 'start' | 'done' | 'error';
  preview: string;
}

const props = defineProps<{
  nodes: TraceNode[];
  running: boolean;
}>();

const labels: Record<string, string> = {
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

const visibleNodes = computed(() => {
  const byId = new Map(props.nodes.map((node) => [node.id, node]));
  return Object.entries(labels).map(([id, name], index) => {
    return {
      ...(byId.get(id) || { id, name, state: 'idle' as const, preview: '' }),
      index: String(index + 1).padStart(2, '0'),
    };
  });
});
</script>
