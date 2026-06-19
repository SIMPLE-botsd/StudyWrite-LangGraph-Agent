<template>
  <div class="model-status">
    <Cpu :size="16" />
    <div class="model-copy">
      <span>{{ config?.provider || 'loading' }}</span>
      <strong>{{ config?.model || '模型读取中' }}</strong>
    </div>
    <i :class="{ ok: config?.has_api_key }">{{ statusText }}</i>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Cpu } from 'lucide-vue-next';
import type { ModelConfig } from '../services/api';

const props = defineProps<{
  config: ModelConfig | null;
}>();

const statusText = computed(() => {
  if (!props.config) return '读取中';
  if (props.config.has_api_key) return props.config.allow_local_fallback ? 'Key 已配置' : '已连接';
  return '本地回退';
});
</script>
