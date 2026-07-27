<script setup lang="ts">
import { computed, onMounted, onUpdated, ref, watchEffect } from 'vue';
import renderMathInElement from 'katex/dist/contrib/auto-render';
import { useWorkspaceStore } from '../../stores/workspace';

import { renderMarkdown } from '../../services/markdown';

const props = defineProps<{
  content: string
}>()

const store = useWorkspaceStore()
const markdownThemeClass = computed(() => `theme-${store.defaultOptions?.markdown_theme || 'academic'}`)

watchEffect(() => {
  const theme = store.defaultOptions?.markdown_theme || 'academic'
  if (theme === 'academic') {
    import('../../themes/academic.css')
  } else if (theme === 'reading') {
    import('../../themes/reading.css')
  } else if (theme === 'geek') {
    import('../../themes/geek.css')
  }
})

const root = ref<HTMLElement | null>(null)

const renderedHtml = computed(() => renderMarkdown(props.content))

const renderMath = () => {
  if (!root.value) return
  renderMathInElement(root.value, {
    delimiters: [
      { left: '$$', right: '$$', display: true },
      { left: '$', right: '$', display: false },
      { left: '\\(', right: '\\)', display: false },
      { left: '\\[', right: '\\]', display: true },
    ],
    throwOnError: false,
    output: 'htmlAndMathml',
  })
}

let mathTimer: ReturnType<typeof setTimeout> | null = null

const scheduleRenderMath = () => {
  if (mathTimer !== null) clearTimeout(mathTimer)
  mathTimer = setTimeout(() => {
    mathTimer = null
    renderMath()
  }, 300)
}

onMounted(() => {
  scheduleRenderMath()
})

onUpdated(() => {
  scheduleRenderMath()
})
</script>

<template>
  <div ref="root" class="markdown-content prose dark:prose-invert max-w-none" :class="markdownThemeClass" v-html="renderedHtml"></div>
</template>
