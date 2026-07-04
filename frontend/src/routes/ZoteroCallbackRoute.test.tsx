import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { ZoteroCallbackRoute } from './ZoteroCallbackRoute';
import { parseCallbackParams } from './zoteroCallbackParams';
import { HOME_PATH } from './paths';

function setLocation(pathAndQuery: string) {
  window.history.replaceState({}, '', pathAndQuery);
}

describe('parseCallbackParams (§8.2 steps 3-4)', () => {
  it('parses a success status', () => {
    expect(parseCallbackParams('?status=success')).toEqual({
      status: 'success',
      code: null,
      message: null,
    });
  });

  it('parses an error status with code/message reusing the ApiError shape', () => {
    expect(
      parseCallbackParams(
        '?status=error&code=zotero_session_mismatch&message=Session%20expired',
      ),
    ).toEqual({
      status: 'error',
      code: 'zotero_session_mismatch',
      message: 'Session expired',
    });
  });

  it('falls back to unknown when status is missing or unrecognized', () => {
    expect(parseCallbackParams('').status).toBe('unknown');
    expect(parseCallbackParams('?status=bogus').status).toBe('unknown');
  });
});

describe('ZoteroCallbackRoute (§11.6 screen shell)', () => {
  afterEach(() => {
    setLocation('/');
  });

  it('renders a success confirmation for ?status=success', () => {
    setLocation('/oauth/zotero/callback?status=success');
    render(<ZoteroCallbackRoute />);
    expect(screen.getByText('Connected to Zotero')).toBeInTheDocument();
  });

  it('renders the provided error message as plain text, never as HTML', () => {
    setLocation(
      '/oauth/zotero/callback?status=error&message=%3Cb%3Ehi%3C%2Fb%3E',
    );
    render(<ZoteroCallbackRoute />);
    // The literal, escaped string must appear as text — not be parsed as
    // a <b> element (regression guard for the no-raw-HTML rule, §6.5/§11.3).
    expect(screen.getByText('<b>hi</b>')).toBeInTheDocument();
    expect(screen.queryByRole('strong')).not.toBeInTheDocument();
  });

  it('renders a pending/unknown state when no status param is present', () => {
    setLocation('/oauth/zotero/callback');
    render(<ZoteroCallbackRoute />);
    expect(screen.getByText('Connecting to Zotero…')).toBeInTheDocument();
  });

  it('"Continue to LitList" navigates back to the app home path', async () => {
    setLocation('/oauth/zotero/callback?status=success');
    render(<ZoteroCallbackRoute />);
    await userEvent.click(
      screen.getByRole('button', { name: /continue to litlist/i }),
    );
    expect(window.location.pathname).toBe(HOME_PATH);
  });
});
