<script setup lang="ts">
import { computed, ref, watch } from 'vue';

const PREVIEW_SIZE = 3;

export interface ReferenceGroupItem {
  id: string;
  title: string;
  secondary: string | null;
  onClick: () => void;
}

const props = defineProps<{
  groupId: string;
  title: string;
  icon: string;
  items: ReferenceGroupItem[];
  resetKey: unknown;
  columnSpan?: 'single' | 'full';
}>();

defineSlots<{
  default(props: { items: ReferenceGroupItem[] }): any;
}>();

const expanded = ref(false);

const visibleItems = computed(() =>
  expanded.value ? props.items : props.items.slice(0, PREVIEW_SIZE)
);

const canToggle = computed(() => props.items.length > PREVIEW_SIZE);

watch(
  () => props.resetKey,
  () => {
    expanded.value = false;
  }
);
</script>

<template>
  <section
    :data-reference-group="groupId"
    :class="[
      columnSpan === 'full' ? 'md:col-span-2' : '',
      'space-y-4',
    ]"
  >
    <div class="flex items-center justify-between gap-3">
      <h4 class="flex items-center gap-2 font-sans text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">
        <span class="material-symbols-outlined text-[14px]">{{ icon }}</span>
        {{ title }}
      </h4>
      <button
        v-if="canToggle"
        :data-reference-toggle="groupId"
        class="font-sans text-[10px] font-bold uppercase tracking-widest text-primary/60 transition-colors hover:text-primary"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Show less' : 'Show all' }}
      </button>
    </div>

    <div
      :class="
        columnSpan === 'full'
          ? 'grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'
          : 'grid grid-cols-1 gap-3'
      "
    >
      <slot :items="visibleItems" />
    </div>
  </section>
</template>
