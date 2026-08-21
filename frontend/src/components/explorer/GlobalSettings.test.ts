import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import GlobalSettings from './GlobalSettings.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('GlobalSettings', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it('establishes a light color scheme inside the sidebar-hosted dialog', async () => {
    const wrapper = mount(GlobalSettings, {
      global: {
        plugins: [createPinia()],
      },
    });

    await wrapper.get('button[title="Global Settings"]').trigger('click');

    expect(wrapper.get('button[title="Global Settings"]').classes()).toContain('global-settings-trigger');
    const dialog = wrapper.get('[role="dialog"]');
    expect(dialog.classes()).toContain('settings-dialog-surface');
    expect(dialog.attributes('aria-modal')).toBe('true');
    expect(dialog.attributes('aria-labelledby')).toBe('system-configuration-title');
  });

  it('saves provider-specific config with provider_id, model and base_url', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    const createCredential = vi.fn().mockResolvedValue(undefined);
    store.createCredential = createCredential as any;

    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Google Gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: '',
      },
      {
        provider_id: 'deepseek',
        provider_type: 'openai_compatible',
        label: 'DeepSeek',
        default_model: 'deepseek-chat',
        models: ['deepseek-chat', 'deepseek-reasoner'],
        allow_custom_model: true,
        requires_base_url: true,
        default_base_url: 'https://api.deepseek.com/v1',
      },
    ] as any;
    store.credentials = [] as any;

    const wrapper = mount(GlobalSettings, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('button[title="Global Settings"]').trigger('click');
    await wrapper.findAll('button').find((button) => button.text().includes('DeepSeek'))!.trigger('click');
    await wrapper.get('input[placeholder="Enter your API key"]').setValue('sk-deepseek');
    await wrapper.get('select[name="default-model"]').setValue('deepseek-reasoner');
    await wrapper.get('input[placeholder="https://api.deepseek.com/v1"]').setValue('https://api.deepseek.com/v1');
    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('Save Provider Config'));
    expect(saveButton).toBeTruthy();
    await saveButton!.trigger('click');

    expect(createCredential).toHaveBeenCalledWith({
      credential_id: 'deepseek',
      provider_type: 'openai_compatible',
      provider_id: 'deepseek',
      api_key: 'sk-deepseek',
      default_model: 'deepseek-reasoner',
      models: ['deepseek-chat', 'deepseek-reasoner'],
      base_url: 'https://api.deepseek.com/v1',
      headers: {},
    });
  });

  it('shows existing configured provider even when provider_id is missing', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Google Gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: '',
      },
    ] as any;
    store.credentials = [
      {
        credential_id: 'gemini',
        provider_type: 'gemini',
        default_model: 'gemini-3-flash-preview',
        has_headers: false,
      },
    ] as any;

    const wrapper = mount(GlobalSettings, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('button[title="Global Settings"]').trigger('click');
    expect(wrapper.text()).toContain('Configured');
    expect(wrapper.text()).toContain('gemini');
  });

  it('shows masked key for configured provider and updates without re-entering key', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    const updateCredential = vi.fn().mockResolvedValue(undefined);
    store.updateCredential = updateCredential as any;
    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Google Gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: '',
      },
    ] as any;
    store.credentials = [
      {
        credential_id: 'gemini',
        provider_type: 'gemini',
        provider_id: 'gemini',
        default_model: 'gemini-3-flash-preview',
        has_headers: false,
      },
    ] as any;

    const wrapper = mount(GlobalSettings, {
      global: {
        plugins: [pinia],
      },
    });
    await wrapper.get('button[title="Global Settings"]').trigger('click');
    expect(wrapper.get('input[type="password"]').attributes('placeholder')).toContain('click to replace');
    await wrapper.get('select[name="default-model"]').setValue('gemini-3-pro-preview');
    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('Save Provider Config'));
    await saveButton!.trigger('click');

    expect(updateCredential).toHaveBeenCalledWith('gemini', {
      provider_type: 'gemini',
      provider_id: 'gemini',
      default_model: 'gemini-3-pro-preview',
      models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
      headers: {},
    });
  });

  it('preserves a saved provider model list without re-adding catalog defaults', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    const updateCredential = vi.fn().mockResolvedValue(undefined);
    store.updateCredential = updateCredential as any;
    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Google Gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: '',
      },
    ] as any;
    store.credentials = [
      {
        credential_id: 'gemini',
        provider_type: 'gemini',
        provider_id: 'gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview'],
        has_headers: false,
      },
    ] as any;

    const wrapper = mount(GlobalSettings, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('button[title="Global Settings"]').trigger('click');
    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('Save Provider Config'));
    await saveButton!.trigger('click');

    expect(updateCredential).toHaveBeenCalledWith('gemini', {
      provider_type: 'gemini',
      provider_id: 'gemini',
      default_model: 'gemini-3-flash-preview',
      models: ['gemini-3-flash-preview'],
      headers: {},
    });
  });

  it('saves the global default knowledge approval policy', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    const updateDefaultOptions = vi.fn().mockResolvedValue(undefined);
    store.updateDefaultOptions = updateDefaultOptions as any;
    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Gemini',
        default_model: 'gemini-2.5-flash',
        models: ['gemini-2.5-flash'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: '',
      },
    ] as any;
    store.credentials = [
      {
        credential_id: 'gemini',
        provider_id: 'gemini',
        provider_type: 'gemini',
        default_model: 'gemini-2.5-flash',
        models: ['gemini-2.5-flash'],
        has_headers: false,
      },
    ] as any;
    store.defaultOptions = {
      conversation_model: {
        provider_id: 'gemini',
        provider_type: 'gemini',
        credential_id: 'gemini',
        model: 'gemini-2.5-flash',
      },
      utility_model: {
        provider_id: 'gemini',
        provider_type: 'gemini',
        credential_id: 'gemini',
        model: 'gemini-2.5-flash',
      },
      markdown_theme: 'academic',
      knowledge_approval_policy: 'agent_decides',
    };

    const wrapper = mount(GlobalSettings, { global: { plugins: [pinia] } });
    await wrapper.get('button[title="Global Settings"]').trigger('click');
    await wrapper.findAll('button').find((button) => button.text().includes('Default Options'))!.trigger('click');
    await wrapper.get('select[aria-label="Default knowledge approval policy"]').setValue('full_auto');
    await wrapper.findAll('button').find((button) => button.text().includes('Save Default Options'))!.trigger('click');

    expect(updateDefaultOptions).toHaveBeenCalledWith(
      expect.objectContaining({ knowledge_approval_policy: 'full_auto' })
    );
  });
});
