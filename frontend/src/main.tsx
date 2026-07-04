import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { Root } from './routes/Root.tsx'

// Routing here is deliberately minimal (§11.6) — see routes/Root.tsx for
// why a full router isn't introduced and how the one real route (the
// Zotero OAuth callback, Task 2A) is handled instead.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
