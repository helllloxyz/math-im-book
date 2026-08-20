const elementForNode = (node: Node | null): Element | null => {
  if (!node) return null
  return node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement
}

const closestKatex = (node: Node | null) => elementForNode(node)?.closest('.katex') || null

const rangeExpandedToKatexBoundaries = (range: Range) => {
  const copyRange = range.cloneRange()
  const startKatex = closestKatex(range.startContainer)
  const endKatex = closestKatex(range.endContainer)
  const startTarget = startKatex?.closest('.katex-display') || startKatex
  const endTarget = endKatex?.closest('.katex-display') || endKatex

  if (startTarget) copyRange.setStartBefore(startTarget)
  if (endTarget) copyRange.setEndAfter(endTarget)

  return copyRange
}

const restoreLatexInFragment = (fragment: ParentNode) => {
  fragment.querySelectorAll('.katex').forEach((formula) => {
    const annotation = formula.querySelector('annotation[encoding="application/x-tex"]')
    if (!annotation) return

    const displayWrapper = formula.closest('.katex-display')
    const delimiter = displayWrapper ? '$$' : '$'
    const replacement = document.createTextNode(
      `${delimiter}${annotation.textContent || ''}${delimiter}`
    )
    const target = displayWrapper || formula
    target.parentNode?.replaceChild(replacement, target)
  })
}

export const selectionTextWithLatex = (selection: Selection | null) => {
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return ''

  const range = rangeExpandedToKatexBoundaries(selection.getRangeAt(0))
  const container = document.createElement('div')
  container.appendChild(range.cloneContents())
  restoreLatexInFragment(container)
  return container.textContent || ''
}

export const selectionIsInsideElement = (
  selection: Selection | null,
  rootElement: Element | null
) => {
  if (!selection || selection.rangeCount === 0 || !rootElement) return false

  const range = selection.getRangeAt(0)
  return (
    rootElement.contains(range.startContainer) &&
    rootElement.contains(range.endContainer)
  )
}

export const copySelectionAsLatex = (
  event: ClipboardEvent,
  rootElement: Element | null,
  selection: Selection | null = window.getSelection()
) => {
  if (!selectionIsInsideElement(selection, rootElement) || !event.clipboardData) return false

  const text = selectionTextWithLatex(selection).trim()
  if (!text) return false

  event.clipboardData.setData('text/plain', text)
  event.preventDefault()
  return true
}
