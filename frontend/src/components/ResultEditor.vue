<template>
  <section class="panel result-panel">
    <div class="panel-head result-head">
      <div>
        <p class="eyebrow">Output</p>
        <h2>写作结果</h2>
      </div>
      <button class="icon-button" type="button" title="复制结果" @click="copy">
        <Copy :size="17" />
      </button>
    </div>

    <textarea
      class="result-editor"
      :value="modelValue"
      placeholder="运行工作流后，这里会显示最终文章和质量自检。"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
  </section>
</template>

<script setup lang="ts">
import { Copy } from 'lucide-vue-next';

const props = defineProps<{ modelValue: string }>();
defineEmits<{ 'update:modelValue': [value: string] }>();

async function copy() {
  await navigator.clipboard.writeText(props.modelValue || '');
}
</script>
