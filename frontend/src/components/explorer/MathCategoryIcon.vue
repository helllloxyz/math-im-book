<template>
  <img
    class="math-category-icon"
    :src="category.iconUrl"
    :alt="decorative ? '' : category.label"
    :aria-hidden="decorative ? 'true' : undefined"
    :data-math-category="category.id"
    draggable="false"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { mathCategoryFor } from './mathCategories';

const props = withDefaults(defineProps<{
  categoryId?: string | null;
  decorative?: boolean;
}>(), {
  categoryId: 'general',
  decorative: true,
});

const category = computed(() => mathCategoryFor(props.categoryId));
</script>
