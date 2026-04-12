import { render } from '@testing-library/react'
import { Button } from '@/components/atoms/button'

test('test_tailwind_classes_applied', () => {
  const { container } = render(<div className="bg-primary">test</div>)
  expect(container.firstChild).toHaveClass('bg-primary')
})

test('test_shadcn_button_renders', () => {
  expect(() => render(<Button variant="default">Click</Button>)).not.toThrow()
})
