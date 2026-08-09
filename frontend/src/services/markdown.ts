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
