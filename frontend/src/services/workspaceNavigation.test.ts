import { describe, expect, it } from 'vitest';
import { buildWorkspaceHref, readWorkspaceTarget } from './workspaceNavigation';

describe('workspaceNavigation', () => {
  it('builds a response-details URL while preserving unrelated query parameters', () => {
    const href = buildWorkspaceHref(
      {
        view: 'details',
        sessionId: 'session/42',
        messageId: 'message 7',
      },
      'https://mathbook.test/app?theme=reading&node=old-node'
    );
    const url = new URL(href);

    expect(url.searchParams.get('theme')).toBe('reading');
    expect(url.searchParams.get('view')).toBe('details');
    expect(url.searchParams.get('session')).toBe('session/42');
    expect(url.searchParams.get('message')).toBe('message 7');
    expect(url.searchParams.has('node')).toBe(false);
  });

  it('reads a library target from a workspace URL', () => {
    expect(
      readWorkspaceTarget('https://mathbook.test/?view=library&session=chat-1&node=node-42')
    ).toEqual({
      view: 'library',
      sessionId: 'chat-1',
      messageId: undefined,
      nodeId: 'node-42',
    });
  });

  it('builds and reads a dedicated knowledge page target', () => {
    const href = buildWorkspaceHref(
      { view: 'knowledge', sessionId: 'chat-1', nodeId: 'node-42' },
      'https://mathbook.test/app?theme=reading'
    );

    expect(readWorkspaceTarget(href)).toEqual({
      view: 'knowledge',
      sessionId: 'chat-1',
      messageId: undefined,
      nodeId: 'node-42',
    });
  });

  it('reads a fork target from a workspace URL', () => {
    expect(
      readWorkspaceTarget('https://mathbook.test/?view=fork&session=chat-1&message=msg-2')
    ).toMatchObject({
      view: 'fork',
      sessionId: 'chat-1',
      messageId: 'msg-2',
    });
  });
});
