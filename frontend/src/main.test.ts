import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  createApp: vi.fn(),
  createPinia: vi.fn(),
  appUse: vi.fn(),
  appMount: vi.fn(),
}));

vi.mock('vue', () => ({
  createApp: mocks.createApp,
}));

vi.mock('pinia', () => ({
  createPinia: mocks.createPinia,
}));

vi.mock('./App.vue', () => ({
  default: { name: 'App' },
}));

describe('main entrypoint', () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';
    mocks.createApp.mockReset();
    mocks.createPinia.mockReset();
    mocks.appUse.mockReset();
    mocks.appMount.mockReset();
    mocks.appUse.mockReturnValue({
      use: mocks.appUse,
      mount: mocks.appMount,
    });
    mocks.createApp.mockReturnValue({
      use: mocks.appUse,
      mount: mocks.appMount,
    });
    mocks.createPinia.mockReturnValue({});
  });

  it('loads KaTeX copy-tex so browser copy uses original LaTeX', async () => {
    await import('./main');

    const container = document.createElement('p');
    container.innerHTML = [
      'Formula: ',
      '<span class="katex">',
      '<span class="katex-mathml">',
      '<math><semantics><mrow></mrow>',
      '<annotation encoding="application/x-tex">\\mathbb{R}^n</annotation>',
      '</semantics></math>',
      '</span>',
      '<span class="katex-html" aria-hidden="true">bad copy text</span>',
      '</span>',
    ].join('');
    document.body.appendChild(container);

    const formula = container.querySelector('.katex');
    expect(formula).not.toBeNull();

    const selection = window.getSelection();
    const range = document.createRange();
    selection?.removeAllRanges();
    range.selectNode(formula as Node);
    selection?.addRange(range);

    const clipboardData = new Map<string, string>();
    const event = new Event('copy', { bubbles: true, cancelable: true }) as ClipboardEvent;
    Object.defineProperty(event, 'clipboardData', {
      value: {
        setData: vi.fn((type: string, value: string) => clipboardData.set(type, value)),
      },
    });

    document.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(clipboardData.get('text/plain')).toBe('$\\mathbb{R}^n$');
  });
});
