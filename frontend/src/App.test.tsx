import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App (Tier 0 scaffolding smoke test)', () => {
  it('renders without crashing', () => {
    render(<App />)
    expect(screen.getByText('LitList')).toBeInTheDocument()
  })
})
