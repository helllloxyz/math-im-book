import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  copySelectionAsLatex,
  selectionIsInsideElement,
  selectionTextWithLatex,
} from './latexSelection'

const katexFormula = (latex: string, visibleText = 'rendered formula') =>
  `<span class="katex"><span class="katex-mathml"><math><semantics><mrow></mrow><annotation encoding="application/x-tex">${latex}</annotation></semantics></math></span><span class="katex-html" aria-hidden="true">${visibleText}</span></span>`

const selectNodeContents = (node: Node) => {
  const selection = window.getSelection()
  const range = document.createRange()
  range.selectNodeContents(node)
  selection?.removeAllRanges()
  selection?.addRange(range)
  return { range, selection }
}

afterEach(() => {
  document.body.innerHTML = ''
  window.getSelection()?.removeAllRanges()
})

describe('LaTeX selection copy', () => {
  it('restores inline and display formulas from KaTeX annotations', () => {
    const root = document.createElement('div')
    root.innerHTML = `
      <p>Inline ${katexFormula('x^2')} follows.</p>
      <div class="katex-display">${katexFormula('\\int_0^1 x\\,dx')}</div>
    `
    document.body.appendChild(root)
    const { selection } = selectNodeContents(root)

    const copiedText = selectionTextWithLatex(selection)

    expect(copiedText).toContain('Inline $x^2$ follows.')
    expect(copiedText).toContain('$$\\int_0^1 x\\,dx$$')
    expect(copiedText).not.toContain('rendered formula')
  })

  it('expands a partial visual formula selection without changing the visible range', () => {
    const root = document.createElement('div')
    root.innerHTML = katexFormula('\\mathbb{R}^n', 'R n')
    document.body.appendChild(root)
    const visibleText = root.querySelector('.katex-html')?.firstChild
    if (!visibleText) throw new Error('KaTeX visual text fixture is missing')

    const selection = window.getSelection()
    const range = document.createRange()
    range.setStart(visibleText, 0)
    range.setEnd(visibleText, 1)
    selection?.removeAllRanges()
    selection?.addRange(range)

    expect(selectionTextWithLatex(selection)).toBe('$\\mathbb{R}^n$')
    expect(range.startContainer).toBe(visibleText)
    expect(range.startOffset).toBe(0)
    expect(range.endContainer).toBe(visibleText)
    expect(range.endOffset).toBe(1)
  })

  it('writes restored LaTeX only for selections contained by the requested source', () => {
    const source = document.createElement('div')
    source.innerHTML = `<p>Space: ${katexFormula('V = \\mathbb{R}^n')}</p>`
    document.body.appendChild(source)
    const { selection } = selectNodeContents(source)
    const clipboardData = new Map<string, string>()
    const event = new Event('copy', { cancelable: true }) as ClipboardEvent
    Object.defineProperty(event, 'clipboardData', {
      value: {
        setData: vi.fn((type: string, value: string) => clipboardData.set(type, value)),
      },
    })

    expect(selectionIsInsideElement(selection, source)).toBe(true)
    expect(copySelectionAsLatex(event, source, selection)).toBe(true)
    expect(event.defaultPrevented).toBe(true)
    expect(clipboardData.get('text/plain')).toContain('$V = \\mathbb{R}^n$')

    const outside = document.createElement('div')
    document.body.appendChild(outside)
    expect(selectionIsInsideElement(selection, outside)).toBe(false)
  })
})
