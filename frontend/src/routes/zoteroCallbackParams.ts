/**
 * Parsing for the Zotero OAuth callback redirect's query params.
 * Split out of ZoteroCallbackRoute.tsx so that file only exports the
 * component (keeps `react-refresh/only-export-components` happy) — see
 * ZoteroCallbackRoute.tsx for the full rationale behind this shape.
 */

export type CallbackStatus = 'success' | 'error' | 'unknown';

export interface ParsedCallback {
  status: CallbackStatus;
  code: string | null;
  message: string | null;
}

export function parseCallbackParams(search: string): ParsedCallback {
  const params = new URLSearchParams(search);
  const status = params.get('status');
  return {
    status: status === 'success' || status === 'error' ? status : 'unknown',
    code: params.get('code'),
    message: params.get('message'),
  };
}
