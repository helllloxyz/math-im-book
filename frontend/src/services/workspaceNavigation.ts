export type WorkspaceView = 'conversation' | 'details' | 'fork' | 'library' | 'knowledge';

export interface WorkspaceTarget {
  view?: WorkspaceView;
  sessionId?: string;
  messageId?: string;
  nodeId?: string;
}

const WORKSPACE_QUERY_KEYS = ['view', 'session', 'message', 'node'] as const;

function currentLocationHref() {
  return typeof window === 'undefined' ? 'http://localhost/' : window.location.href;
}

export function buildWorkspaceHref(
  target: WorkspaceTarget,
  baseHref = currentLocationHref()
) {
  const url = new URL(baseHref);

  for (const key of WORKSPACE_QUERY_KEYS) {
    url.searchParams.delete(key);
  }

  if (target.view) url.searchParams.set('view', target.view);
  if (target.sessionId) url.searchParams.set('session', target.sessionId);
  if (target.messageId) url.searchParams.set('message', target.messageId);
  if (target.nodeId) url.searchParams.set('node', target.nodeId);

  return url.toString();
}

export function readWorkspaceTarget(href = currentLocationHref()): WorkspaceTarget {
  const url = new URL(href);
  const rawView = url.searchParams.get('view');
  const view = ['conversation', 'details', 'fork', 'library', 'knowledge'].includes(rawView || '')
    ? (rawView as WorkspaceView)
    : undefined;

  return {
    view,
    sessionId: url.searchParams.get('session') || undefined,
    messageId: url.searchParams.get('message') || undefined,
    nodeId: url.searchParams.get('node') || undefined,
  };
}
