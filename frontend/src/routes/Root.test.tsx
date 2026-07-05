import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Root } from './Root';
import { createTestQueryClient, wrapperWithClient } from '../api/testUtils';

function setLocation(pathAndQuery: string) {
  window.history.replaceState({}, '', pathAndQuery);
}

describe('Root routing (§11.6 — one real route, no general router)', () => {
  afterEach(() => {
    setLocation('/');
  });

  it('renders the main app shell at the home path', () => {
    setLocation('/');
    const client = createTestQueryClient();
    render(<Root />, { wrapper: wrapperWithClient(client) });
    expect(screen.getByText('LitList')).toBeInTheDocument();
  });

  it('renders the Zotero OAuth callback shell at its fixed path', () => {
    setLocation('/oauth/zotero/callback?status=success');
    render(<Root />);
    expect(screen.getByText('Connected to Zotero')).toBeInTheDocument();
  });

  it('renders the main app shell for any other path (no 404 route)', () => {
    setLocation('/some/unrelated/path');
    const client = createTestQueryClient();
    render(<Root />, { wrapper: wrapperWithClient(client) });
    expect(screen.getByText('LitList')).toBeInTheDocument();
  });
});
