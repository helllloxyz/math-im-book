import { describe, expect, it } from 'vitest';

import { renderMarkdown } from './markdown';

describe('renderMarkdown', () => {
  it('preserves escaped LaTeX delimiters for KaTeX auto-render', () => {
    const html = renderMarkdown(
      '- **低维例子**：球面 \\(S^2\\)、三维空间 \\(\\mathbb{R}^3\\) 本身。\n' +
        '- **高维例子**：\\[\\mathbb{CP}^n\\]'
    );

    expect(html).toContain('\\(S^2\\)');
    expect(html).toContain('\\(\\mathbb{R}^3\\)');
    expect(html).toContain('\\[\\mathbb{CP}^n\\]');
  });
});
