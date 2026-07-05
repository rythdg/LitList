import { useSaved } from "../../api/saved";
import { ZoteroPushFlow } from "../../components/screens/ZoteroPushFlow";
import { useZoteroPushFlowStore } from "../../state/zoteroPushFlowStore";
import { useZoteroPushFlowController } from "./useZoteroPushFlowController";

/**
 * Task 4B: self-contained drop-in for `App.tsx`'s Saved List panel
 * (§5.4/§5.5) — reads the Saved List's own PMIDs (`useSaved`) and the
 * push-flow-open flag (`zoteroPushFlowStore`, which also handles the
 * OAuth-round-trip "reopen after connecting" hand-off, see that store's
 * docstring) and renders nothing when the flow isn't open. Kept as its
 * own component (rather than inlined into `App.tsx`) specifically so
 * `App.tsx`'s own composition (Task 4A) only needs one extra line to
 * pick this up, without needing to know any of this flow's internal
 * step machinery.
 */
export function ZoteroPushModal() {
  const isOpen = useZoteroPushFlowStore((state) => state.isOpen);
  const close = useZoteroPushFlowStore((state) => state.close);
  const saved = useSaved();

  const pmids = saved.data?.items.map((item) => item.pmid) ?? [];

  const flowProps = useZoteroPushFlowController({ pmids, onClose: close });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Save to Zotero"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40"
    >
      <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
        <ZoteroPushFlow {...flowProps} />
      </div>
    </div>
  );
}
