<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'

const props = defineProps<{
  text: string
  displayMode?: boolean
}>()

const renderedHtml = computed(() => {
  try {
    return katex.renderToString(props.text, {
      displayMode: props.displayMode || false,
      throwOnError: false,
      output: 'htmlAndMathml',
    })
  } catch (e) {
    console.error('KaTeX error:', e)
    return props.text
  }
})
</script>

<template>
  <span v-if="!displayMode" v-html="renderedHtml" class="inline-flex items-baseline align-middle"></span>
  <div v-else class="math-surface overflow-x-auto shadow-sm" v-html="renderedHtml"></div>
</template>

<style>
/* KaTeX specific adjustments to maintain scholarly rigor */
.katex-display {
  margin: 0 !important;
}
.katex {
  font-size: 1.05em;
  @apply font-serif;
}
</style>
