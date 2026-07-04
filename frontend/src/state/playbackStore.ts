import { create } from "zustand";

/**
 * Local-only playback UI state (§11.2): whether narration is playing,
 * the mute toggle, and the currently-highlighted sentence index. This
 * store has no backend counterpart, ever — it is *not* the playback
 * engine itself (§11.3's `usePlaybackEngine` owns the actual
 * `SpeechSynthesisUtterance` queue/timers as private internal state);
 * this store is the piece of that engine's state that UI components
 * (play/pause button, mute icon, highlighted `<span>`) need to read and
 * re-render on, without every component reaching into the engine's
 * internals directly.
 */
export interface PlaybackState {
  isPlaying: boolean;
  isMuted: boolean;
  /** Index into the current paper's `AbstractSegment[]` (CONTRACTS.md §1)
   * — the sync signal is this field, never `onboundary` events (§6.5:
   * those are bonus-only precision). `null` when nothing is highlighted
   * yet (e.g. before playback starts, per §5.3's collapsed-abstract
   * rule). */
  highlightedSegmentIndex: number | null;

  play: () => void;
  pause: () => void;
  togglePlayPause: () => void;
  toggleMute: () => void;
  setHighlightedSegmentIndex: (index: number | null) => void;
  /** Reset to the pre-playback state — called when advancing to a new
   * paper (§5.3b), since the highlight/play state is per-paper, not
   * carried across the swipe. */
  resetForNewPaper: () => void;
}

export const usePlaybackStore = create<PlaybackState>((set) => ({
  isPlaying: false,
  isMuted: false,
  highlightedSegmentIndex: null,

  play: () => set({ isPlaying: true }),
  pause: () => set({ isPlaying: false }),
  togglePlayPause: () => set((state) => ({ isPlaying: !state.isPlaying })),
  // Mute affects audio output only (§5.3) — it never touches isPlaying.
  toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
  setHighlightedSegmentIndex: (index) => set({ highlightedSegmentIndex: index }),
  resetForNewPaper: () => set({ isPlaying: false, highlightedSegmentIndex: null }),
}));
