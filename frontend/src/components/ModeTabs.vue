<template>
  <div class="mode-tabs" role="tablist">
    <button
      v-for="item in items"
      :key="item.value"
      class="mode-tab"
      :class="{ active: modelValue === item.value }"
      type="button"
      @click="$emit('update:modelValue', item.value)"
    >
      <component :is="item.icon" :size="16" />
      <span>{{ item.label }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { FilePenLine, Paintbrush, Repeat2 } from 'lucide-vue-next';

defineProps<{ modelValue: string }>();
defineEmits<{ 'update:modelValue': [value: string] }>();

const items = [
  { value: 'draft', label: '起草', icon: FilePenLine },
  { value: 'polish', label: '润色', icon: Paintbrush },
  { value: 'imitate', label: '仿写', icon: Repeat2 },
];
</script>
