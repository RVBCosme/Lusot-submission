// jsdom has <dialog> but not showModal() or close(). This gives them their effect that tests can see: the open
// attribute, and the close event. In a browser the same calls also put the dialog in the top layer, which the
// browser checks in Task 18's end-to-end suite, not here.
export function polyfillDialog(): void {
  const proto = HTMLDialogElement.prototype
  if (typeof proto.showModal === 'function') return
  proto.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  proto.close = function close(this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}
