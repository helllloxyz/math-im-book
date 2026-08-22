import { describe, expect, it } from 'vitest';

import {
  extractMarkdownHeadings,
  renderMarkdown,
  splitMarkdownByCitations,
} from './markdown';

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

  it('renders strong labels ending in punctuation before Chinese text', () => {
    const html = renderMarkdown('**迹（Trace）**在数学中表示线性变换的对角和。');

    expect(html).toContain('<strong>迹（Trace）</strong>在数学中');
    expect(html).not.toContain('**迹（Trace）**');
  });

  it('keeps adjacent strong spans well formed after a Chinese boundary', () => {
    const html = renderMarkdown(
      '从一个**抽象群**到**线性变换群（或可逆矩阵群）**的**同态映射**。'
    );

    expect(html).toContain(
      '从一个<strong>抽象群</strong>到<strong>线性变换群（或可逆矩阵群）</strong>的<strong>同态映射</strong>。'
    );
  });

  it('leaves the same strong-looking text untouched inside inline code', () => {
    const html = renderMarkdown('`**迹（Trace）**在`');

    expect(html).toContain('<code>**迹（Trace）**在</code>');
  });
});

describe('extractMarkdownHeadings', () => {
  it('extracts a clean hierarchy from ATX and setext headings', () => {
    expect(extractMarkdownHeadings(
      '# Overview\n\nBody\n\n## **Core idea**\n\nMore body\n\nApplications\n---\n'
    )).toEqual([
      { level: 1, text: 'Overview' },
      { level: 2, text: 'Core idea' },
      { level: 2, text: 'Applications' },
    ]);
  });

  it('ignores heading-like text inside code blocks', () => {
    expect(extractMarkdownHeadings('```md\n# Not a section\n```\n\n## Real section')).toEqual([
      { level: 2, text: 'Real section' },
    ]);
  });
});

describe('splitMarkdownByCitations', () => {
  it('places each citation immediately after the Markdown block that mentions it', () => {
    expect(splitMarkdownByCitations(
      '第一段使用定义。[K1]\n\n第二段继续推导。\n\n最后使用定理。[K2]',
      2
    )).toEqual([
      { content: '第一段使用定义。[K1]', citationIndexes: [0] },
      { content: '\n第二段继续推导。\n\n最后使用定理。[K2]', citationIndexes: [1] },
    ]);
  });

  it('does not treat citation-like text in a code block as a reference', () => {
    expect(splitMarkdownByCitations('```text\n[K1]\n```\n\n正文。', 1)).toEqual([
      { content: '```text\n[K1]\n```\n\n正文。', citationIndexes: [0] },
    ]);
  });

  it('keeps uncited referenced nodes available after the answer as a fallback', () => {
    expect(splitMarkdownByCitations('正文没有显式标记。', 2)).toEqual([
      { content: '正文没有显式标记。', citationIndexes: [0, 1] },
    ]);
  });
});
