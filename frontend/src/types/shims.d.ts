declare module 'katex/dist/contrib/auto-render' {
  interface RenderMathDelimiter {
    left: string;
    right: string;
    display: boolean;
  }

  interface RenderMathOptions {
    delimiters?: RenderMathDelimiter[];
    throwOnError?: boolean;
    ignoredTags?: string[];
    ignoredClasses?: string[];
    output?: 'html' | 'mathml' | 'htmlAndMathml';
  }

  export default function renderMathInElement(
    element: HTMLElement,
    options?: RenderMathOptions
  ): void;
}

declare module '*.css' {
  const content: { [className: string]: string };
  export default content;
}
