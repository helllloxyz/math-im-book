import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAxiosClient = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    create: () => mockAxiosClient,
  },
}));

import { api } from './api';

function streamResponse(chunks: string[], contentType = 'text/event-stream') {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    ok: true,
    status: 200,
    headers: {
      get(name: string) {
        return name.toLowerCase() === 'content-type' ? contentType : null;
      },
    },
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) {
              return { done: true, value: undefined };
            }
            const value = encoder.encode(chunks[index]);
            index += 1;
            return { done: false, value };
          },
        };
      },
    },
  } as unknown as Response;
}

describe('api.askStream', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends conversation_model without provider_profile', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        streamResponse([
          'event: final\r\n',
          'data: {"answer":{"assistant_text":"ok"},"session":{"messages":[],"branch":{"active_node_ids":[],"summary_node_ids":[],"active_symbols":{}}}}\r\n\r\n',
        ])
      );

    await api.askStream(
      'Explain this',
      undefined,
      {
        provider_id: 'deepseek',
        provider_type: 'openai_compatible',
        model: 'deepseek-chat',
        credential_id: 'deepseek',
      },
      undefined,
      undefined,
      {},
      'scope-analysis',
      'full_auto'
    );

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    const body = JSON.parse(String((init as any).body));
    expect(body.provider_profile).toBeUndefined();
    expect(body.conversation_model).toEqual({
      provider_id: 'deepseek',
      provider_type: 'openai_compatible',
      model: 'deepseek-chat',
      credential_id: 'deepseek',
    });
    expect(body.knowledge_scope_id).toBe('scope-analysis');
    expect(body.knowledge_approval_policy).toBe('full_auto');
  });

  it('parses SSE responses separated by CRLF boundaries', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      streamResponse([
        'event: chunk\r\n',
        'data: {"delta":"Hello"}\r\n\r\n',
        'event: final\r\n',
        'data: {"answer":{"assistant_text":"Hello"},"session":{"messages":[],"branch":{"active_node_ids":[],"summary_node_ids":[],"active_symbols":{}}}}\r\n\r\n',
      ])
    );

    const onChunk = vi.fn();
    const response = await api.askStream('Explain this', undefined, undefined, undefined, undefined, {
      onChunk,
    });

    expect(onChunk).toHaveBeenCalledWith('Hello');
    expect(response.answer.assistant_text).toBe('Hello');
  });

  it('delivers Agent progress events before answer chunks', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      streamResponse([
        'event: progress\r\n',
        'data: {"stage":"searching","label":"正在检索知识索引","detail":"检查 12 个节点","state":"running"}\r\n\r\n',
        'event: chunk\r\n',
        'data: {"delta":"Answer"}\r\n\r\n',
        'event: final\r\n',
        'data: {"answer":{"assistant_text":"Answer"},"session":{"messages":[],"branch":{"active_node_ids":[],"summary_node_ids":[],"active_symbols":{}}}}\r\n\r\n',
      ])
    );
    const onProgress = vi.fn();
    const onChunk = vi.fn();

    await api.askStream('Explain this', undefined, undefined, undefined, undefined, {
      onProgress,
      onChunk,
    });

    expect(onProgress).toHaveBeenCalledWith({
      stage: 'searching',
      label: '正在检索知识索引',
      detail: '检查 12 个节点',
      state: 'running',
    });
    expect(onChunk).toHaveBeenCalledWith('Answer');
  });
});

describe('api explorer client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches explorer trees', async () => {
    mockAxiosClient.get
      .mockResolvedValueOnce({ data: { scope: 'sessions', tree: [] } })
      .mockResolvedValueOnce({ data: { scope: 'knowledge', tree: [] } });

    const sessions = await api.getSessionExplorer();
    const knowledge = await api.getKnowledgeExplorer();

    expect(mockAxiosClient.get).toHaveBeenNthCalledWith(1, '/explorer/sessions');
    expect(mockAxiosClient.get).toHaveBeenNthCalledWith(2, '/explorer/knowledge');
    expect(sessions.scope).toBe('sessions');
    expect(knowledge.scope).toBe('knowledge');
  });

  it('updates explorer item icons', async () => {
    mockAxiosClient.patch.mockResolvedValueOnce({
      data: {
        icon: {
          item_type: 'knowledge_node',
          item_id: 'linear-map',
          icon: 'wave',
          updated_at: '2026-04-20T00:00:00Z',
        },
      },
    });

    const icon = await api.updateExplorerItemIcon('knowledge_node', 'linear-map', 'wave');

    expect(mockAxiosClient.patch).toHaveBeenCalledWith(
      '/explorer/items/knowledge_node/linear-map/icon',
      { icon: 'wave' }
    );
    expect(icon.icon).toBe('wave');
  });
});

describe('api knowledge approval', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('rejects suggested drafts through the message approval endpoint', async () => {
    mockAxiosClient.post.mockResolvedValueOnce({
      data: { session_id: 'chat-1', messages: [] },
    });

    await api.rejectSuggestedDrafts('chat-1', 'msg-a');

    expect(mockAxiosClient.post).toHaveBeenCalledWith(
      '/sessions/chat-1/messages/msg-a/suggested-drafts/reject'
    );
  });
});
