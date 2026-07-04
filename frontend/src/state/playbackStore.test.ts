import { beforeEach, describe, expect, it } from "vitest";
import { usePlaybackStore } from "./playbackStore";

const initialState = usePlaybackStore.getInitialState();

describe("usePlaybackStore (§11.2 local-only playback state)", () => {
  beforeEach(() => {
    usePlaybackStore.setState(initialState, true);
  });

  it("starts paused, unmuted, with no highlighted segment", () => {
    const state = usePlaybackStore.getState();
    expect(state.isPlaying).toBe(false);
    expect(state.isMuted).toBe(false);
    expect(state.highlightedSegmentIndex).toBeNull();
  });

  it("play()/pause() set isPlaying directly", () => {
    usePlaybackStore.getState().play();
    expect(usePlaybackStore.getState().isPlaying).toBe(true);

    usePlaybackStore.getState().pause();
    expect(usePlaybackStore.getState().isPlaying).toBe(false);
  });

  it("togglePlayPause() flips isPlaying", () => {
    usePlaybackStore.getState().togglePlayPause();
    expect(usePlaybackStore.getState().isPlaying).toBe(true);
    usePlaybackStore.getState().togglePlayPause();
    expect(usePlaybackStore.getState().isPlaying).toBe(false);
  });

  it("toggleMute() never changes isPlaying (§5.3: mute is audio-output-only)", () => {
    usePlaybackStore.getState().play();
    usePlaybackStore.getState().toggleMute();

    const state = usePlaybackStore.getState();
    expect(state.isMuted).toBe(true);
    expect(state.isPlaying).toBe(true);
  });

  it("setHighlightedSegmentIndex() sets the sync signal directly, independent of onboundary events", () => {
    usePlaybackStore.getState().setHighlightedSegmentIndex(3);
    expect(usePlaybackStore.getState().highlightedSegmentIndex).toBe(3);

    usePlaybackStore.getState().setHighlightedSegmentIndex(null);
    expect(usePlaybackStore.getState().highlightedSegmentIndex).toBeNull();
  });

  it("resetForNewPaper() clears play + highlight state on advance (§5.3b)", () => {
    usePlaybackStore.getState().play();
    usePlaybackStore.getState().setHighlightedSegmentIndex(5);

    usePlaybackStore.getState().resetForNewPaper();

    const state = usePlaybackStore.getState();
    expect(state.isPlaying).toBe(false);
    expect(state.highlightedSegmentIndex).toBeNull();
  });

  it("resetForNewPaper() does not reset mute — mute is a user preference, not per-paper state", () => {
    usePlaybackStore.getState().toggleMute();
    usePlaybackStore.getState().resetForNewPaper();
    expect(usePlaybackStore.getState().isMuted).toBe(true);
  });
});
