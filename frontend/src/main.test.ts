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

  it('mounts the app with Pinia', async () => {
    await import('./main');

    expect(mocks.createApp).toHaveBeenCalledWith({ name: 'App' });
    expect(mocks.appUse).toHaveBeenCalledWith({});
    expect(mocks.appMount).toHaveBeenCalledWith('#app');
  });
});
