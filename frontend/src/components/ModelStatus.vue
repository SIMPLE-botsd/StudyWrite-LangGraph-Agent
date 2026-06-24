<template>
  <div class="model-status">
    <Cpu :size="16" />
    <div class="model-copy">
      <span>{{ config?.provider || 'loading' }}</span>
      <strong>{{ config?.model || '模型读取中' }}</strong>
    </div>
    <i :class="{ ok: config?.used_llm, warn: config?.used_fallback || Boolean(config?.last_error) }" :title="config?.last_error || ''">
      {{ statusText }}
    </i>
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
  if (props.config.used_llm) return 'LLM 已调用';
  if (props.config.last_error) return '模型错误';
  if (props.config.used_fallback) return '本地回退';
  if (props.config.has_api_key) return props.config.allow_local_fallback ? 'Key 已配置' : '已连接';
  return '本地回退';
});
</script>
