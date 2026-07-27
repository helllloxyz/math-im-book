import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
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
