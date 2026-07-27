import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import MathText from './MathText.vue';

describe('MathText', () => {
  it('renders formulas with original LaTeX available to browser selection', () => {
    const wrapper = mount(MathText, {
      props: {
        text: 'x^2',
        displayMode: true,
      },
    });

    const annotation = wrapper.element.querySelector(
      'annotation[encoding="application/x-tex"]'
    );
    expect(annotation?.textContent).toBe('x^2');
  });
});
