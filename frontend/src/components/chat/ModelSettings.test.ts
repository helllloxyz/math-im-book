import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ModelSettings from './ModelSettings.vue';
import { useWorkspaceStore } from '../../stores/workspace';

describe('ModelSettings', () => {
  beforeEach(() => {
    const pinia = createPinia();
    setActivePinia(pinia);
  });

  it('only lists configured provider/model entries from GlobalSettings', async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useWorkspaceStore();
    store.providerOptions = [
      {
        provider_type: 'gemini',
        label: 'Google Gemini',
        default_model: 'gemini-3-flash-preview',
        models: ['gemini-3-flash-preview', 'gemini-3-pro-preview'],
        allow_custom_model: false,
        requires_base_url: false,
        default_base_url: null,
      },
      {
        provider_type: 'openai_compatible',
        label: 'OpenAI Compatible',
        default_model: 'gpt-5.1',
        models: ['gpt-5.1', 'deepseek-chat'],
        allow_custom_model: true,
        requires_base_url: true,
        default_base_url: 'https://api.openai.com/v1',
      },
    ] as any;
    store.providerCatalog = [
      {
        provider_id: 'gemini',
        provider_type: 'gemini',
        label: 'Gemini',
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
    store.credentials = [
      {
        credential_id: 'gemini-main',
        provider_type: 'gemini',
        provider_id: 'gemini',
        default_model: 'gemini-3-pro-preview',
        has_headers: false,
      },
      {
        credential_id: 'deepseek-main',
        provider_type: 'openai_compatible',
        provider_id: 'deepseek',
        default_model: 'deepseek-chat',
        base_url: 'https://api.deepseek.com/v1',
        has_headers: false,
      },
    ] as any;
    store.selectedProviderProfile = {
      provider_type: 'gemini',
      model: 'gemini-3-flash-preview',
      credential_id: 'gemini-main',
    } as any;

    const wrapper = mount(ModelSettings, {
      global: {
        plugins: [pinia],
      },
    });

    await wrapper.get('button[title="Model Settings"]').trigger('click');
    const selects = wrapper.findAll('select');
    expect(selects.length).toBe(1);
    expect(wrapper.text()).toContain('gemini-3-pro-preview');
    expect(wrapper.text()).toContain('deepseek-chat');
    expect(wrapper.text()).not.toContain('gpt-5.1');
  });
});
