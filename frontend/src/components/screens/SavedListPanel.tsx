/**
 * Screen D — Saved List Panel (SPEC.md §5.4, §9.6 "Disconnect Zotero").
 */
import { isRetracted, type Paper } from "./types";

export interface SavedListPanelProps {
  savedPapers: Paper[];
  isZoteroConnected: boolean;
  onRemove: (pmid: string) => void;
  onPushToZotero: () => void;
  onDownloadCsv: () => void;
  /** §9.6/§5.4: deletes the local ZoteroConnection immediately — required
   *  so the OAuth relationship isn't a one-way door with no way back. */
  onDisconnectZotero: () => void;
  onClose: () => void;
}

function metadataLine(paper: Paper): string {
  const year = paper.pub_date?.split(" ")[0];
  return [paper.last_author ? `${paper.last_author} et al.` : null, year]
    .filter(Boolean)
    .join(" · ");
}

export function SavedListPanel({
  savedPapers,
  isZoteroConnected,
  onRemove,
  onPushToZotero,
  onDownloadCsv,
  onDisconnectZotero,
  onClose,
}: SavedListPanelProps) {
  const isEmpty = savedPapers.length === 0;

  return (
    <div className="flex min-h-screen flex-col gap-4 bg-white p-4 text-slate-900">
      <button
        type="button"
        onClick={onClose}
        aria-label="Swipe down to collapse"
        className="text-sm text-slate-500"
      >
        ⌄ swipe down to collapse
      </button>

      <h2 className="font-semibold">Saved this session ({savedPapers.length})</h2>

      {isEmpty ? (
        <p className="text-sm text-slate-500" data-testid="saved-empty-copy">
          Papers you mark Interested will show up here.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {savedPapers.map((paper) => (
            <li
              key={paper.pmid}
              className="flex items-center justify-between border-b border-slate-100 pb-2"
            >
              <div>
                <p className="font-medium">
                  {paper.title}
                  {isRetracted(paper) ? (
                    <span
                      data-testid={`retracted-badge-${paper.pmid}`}
                      className="ml-2 text-sm font-medium text-red-800"
                    >
                      ⚠ Retracted
                    </span>
                  ) : null}
                </p>
                <p className="text-sm text-slate-600">{metadataLine(paper)}</p>
              </div>
              <button
                type="button"
                onClick={() => onRemove(paper.pmid)}
                aria-label={`Remove ${paper.title} from saved list`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex flex-col gap-2">
        <button
          type="button"
          onClick={onPushToZotero}
          disabled={isEmpty}
          className="rounded bg-slate-900 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Push to Zotero
        </button>
        <button
          type="button"
          onClick={onDownloadCsv}
          disabled={isEmpty}
          className="rounded border border-slate-300 px-4 py-2 disabled:cursor-not-allowed disabled:text-slate-400"
        >
          Download CSV
        </button>

        {isZoteroConnected ? (
          <>
            <p className="text-sm text-slate-500">Connected to Zotero as you</p>
            <button
              type="button"
              onClick={onDisconnectZotero}
              data-testid="disconnect-zotero-button"
              className="rounded border border-red-300 px-4 py-2 text-sm text-red-700"
            >
              Disconnect Zotero
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
