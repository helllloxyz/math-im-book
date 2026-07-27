export interface ContentPart {
  type: 'text' | 'inline' | 'display';
  content: string;
}

/**
 * Robustly parses text with LaTeX expressions into content parts.
 * Replaces $ ... $ with inline math and $$ ... $$ with display math.
 */
export function parseMath(content: string): ContentPart[] {
  const parts: ContentPart[] = [];
  const regex = /(\$\$[\s\S]*?\$\$|\$.*?\$)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', content: content.substring(lastIndex, match.index) });
    }
    const math = match[0];
    if (math.startsWith('$$')) {
      parts.push({ type: 'display', content: math.substring(2, math.length - 2).trim() });
    } else {
      parts.push({ type: 'inline', content: math.substring(1, math.length - 1).trim() });
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < content.length) {
    parts.push({ type: 'text', content: content.substring(lastIndex) });
  }
  return parts;
}
