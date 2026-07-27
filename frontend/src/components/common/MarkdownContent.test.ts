import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import { describe, expect, it, vi } from 'vitest';

import MarkdownContent from './MarkdownContent.vue';

describe('MarkdownContent', () => {
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
