import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
});

const cjkCharacter = /\p{Script=Han}/u;
const punctuationCharacter = /\p{P}/u;

export interface MarkdownHeading {
  level: number;
  text: string;
}

export interface MarkdownCitationSection {
  content: string;
  citationIndexes: number[];
}

// CommonMark does not treat `**术语（Term）**在……` as strong emphasis because
// the closing delimiter sits between punctuation and a CJK character. Accept
// that common Chinese writing pattern without requiring a visible space.
markdown.inline.ruler.before('emphasis', 'cjk-strong-boundary', (state, silent) => {
  const start = state.pos;
  if (state.src.slice(start, start + 2) !== '**') return false;

  const end = state.src.indexOf('**', start + 2);
  if (end < 0) return false;

  const content = state.src.slice(start + 2, end);
  const nextCharacter = state.src.slice(end + 2).match(/^./u)?.[0] || '';
  const lastCharacter = content.match(/.$/u)?.[0] || '';
  if (
    !content ||
    /^\s/u.test(content) ||
    /\s$/u.test(content) ||
    !punctuationCharacter.test(lastCharacter) ||
    !cjkCharacter.test(nextCharacter)
  ) {
    return false;
  }

  if (!silent) {
    state.push('strong_open', 'strong', 1);
    state.push('text', '', 0).content = content;
    state.push('strong_close', 'strong', -1);
  }
  state.pos = end + 2;
  return true;
});

export function renderMarkdown(content: string): string {
  const mathBlocks: string[] = [];
  const placeholderRegex = /MATHIMBOOKMATHBLOCK(\d+)X/g;
  const preserveMath = (text: string, pattern: RegExp) =>
    text.replace(pattern, (match) => {
      mathBlocks.push(match);
      return `MATHIMBOOKMATHBLOCK${mathBlocks.length - 1}X`;
    });
  
  // 1. Extract math and replace with placeholders
  let text = content || '';
  
  // Display math: $$ ... $$
  text = preserveMath(text, /\$\$([\s\S]*?)\$\$/g);

  // Display math: \[ ... \]
  text = preserveMath(text, /\\\[([\s\S]*?)\\\]/g);

  // Inline math: \( ... \)
  text = preserveMath(text, /\\\(([\s\S]*?)\\\)/g);
  
  // Inline math: $ ... $ (ignoring escaped $)
  text = preserveMath(text, /\$((?:\\.|[^$\\])+)\$/g);

  // 2. Render markdown
  let rendered = markdown.render(text);

  // 3. Sanitize HTML (do this BEFORE restoring math to prevent DOMPurify from stripping `<` or `>` in math)
  rendered = DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true },
  });

  // 4. Restore math blocks
  rendered = rendered.replace(placeholderRegex, (match, p1) => {
    return mathBlocks[parseInt(p1, 10)];
  });

  return rendered;
}

export function extractMarkdownHeadings(content: string): MarkdownHeading[] {
  const tokens = markdown.parse(content || '', {});
  const headings: MarkdownHeading[] = [];

  tokens.forEach((token, index) => {
    if (token.type !== 'heading_open') return;

    const inlineToken = tokens[index + 1];
    const text = (inlineToken?.children || [])
      .map((child) => {
        if (child.type === 'softbreak' || child.type === 'hardbreak') return ' ';
        return child.content;
      })
      .join('')
      .replace(/\s+/g, ' ')
      .trim();

    if (text) {
      headings.push({
        level: Number.parseInt(token.tag.slice(1), 10),
        text,
      });
    }
  });

  return headings;
}

export function splitMarkdownByCitations(
  content: string,
  citationCount: number
): MarkdownCitationSection[] {
  const source = content || '';
  if (!source) return [{ content: '', citationIndexes: [] }];
  if (citationCount <= 0) return [{ content: source, citationIndexes: [] }];

  const lines = source.split('\n');
  const tokens = markdown.parse(source, {});
  const rootBlocks = tokens.filter(
    (token) => token.level === 0 && token.map && token.map[1] > token.map[0]
  );
  const placed = new Set<number>();
  const sections: MarkdownCitationSection[] = [];
  let sectionStart = 0;

  for (const block of rootBlocks) {
    const [blockStart, blockEnd] = block.map!;
    const citationIndexes: number[] = [];
    const inlineTokens = tokens.filter(
      (token) =>
        token.type === 'inline' &&
        token.map &&
        token.map[0] >= blockStart &&
        token.map[1] <= blockEnd
    );

    for (const inlineToken of inlineTokens) {
      const text = (inlineToken.children || [])
        .filter((child) => child.type === 'text')
        .map((child) => child.content)
        .join('');
      for (const match of text.matchAll(/\[K(\d+)\]/gi)) {
        const citationIndex = Number.parseInt(match[1], 10) - 1;
        if (
          citationIndex >= 0 &&
          citationIndex < citationCount &&
          !placed.has(citationIndex)
        ) {
          placed.add(citationIndex);
          citationIndexes.push(citationIndex);
        }
      }
    }

    if (!citationIndexes.length) continue;
    sections.push({
      content: lines.slice(sectionStart, blockEnd).join('\n'),
      citationIndexes,
    });
    sectionStart = blockEnd;
  }

  if (sectionStart < lines.length || !sections.length) {
    sections.push({
      content: lines.slice(sectionStart).join('\n'),
      citationIndexes: [],
    });
  }

  const unplaced = Array.from({ length: citationCount }, (_, index) => index)
    .filter((index) => !placed.has(index));
  if (unplaced.length) {
    sections[sections.length - 1].citationIndexes.push(...unplaced);
  }

  return sections;
}
