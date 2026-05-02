import '@testing-library/jest-dom'

// JSDOM stubs so libs that touch DOM observers don't blow up at import time.
// cmdk + Radix Popover both poke at ResizeObserver / pointer-capture APIs.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  ;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub
}

// Radix Popover calls these on its trigger; JSDOM elements don't have them.
if (typeof Element !== 'undefined') {
  const proto = Element.prototype as unknown as Record<string, unknown>
  if (typeof proto.hasPointerCapture !== 'function') {
    proto.hasPointerCapture = () => false
  }
  if (typeof proto.setPointerCapture !== 'function') {
    proto.setPointerCapture = () => undefined
  }
  if (typeof proto.releasePointerCapture !== 'function') {
    proto.releasePointerCapture = () => undefined
  }
  if (typeof proto.scrollIntoView !== 'function') {
    proto.scrollIntoView = () => undefined
  }
}
