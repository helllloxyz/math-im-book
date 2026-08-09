import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it, vi } from 'vitest';

import MarkdownContent from './MarkdownContent.vue';

describe('MarkdownContent', () => {
  it('keeps the light reading surface independent of the system dark preference', () => {
    const wrapper = mount(MarkdownContent, {
      props: {
        content: '# 标题\n\n**重点**',
      },
      global: {
        plugins: [createPinia()],
      },
    });

    expect(wrapper.classes()).toContain('prose');
    expect(wrapper.classes()).not.toContain('dark:prose-invert');
  });

  it('renders Markdown formulas with original LaTeX available to browser selection', async () => {
    vi.useFakeTimers();

    const wrapper = mount(MarkdownContent, {
      props: {
        content: 'Euler: $e^{i\\pi} + 1 = 0$',
      },
      global: {
        plugins: [createPinia()],
      },
    });

    await vi.advanceTimersByTimeAsync(300);

    const annotation = wrapper.element.querySelector(
      'annotation[encoding="application/x-tex"]'
    );
    expect(annotation?.textContent).toBe('e^{i\\pi} + 1 = 0');

    vi.useRealTimers();
  });
});
