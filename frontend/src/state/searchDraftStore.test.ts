import { beforeEach, describe, expect, it } from "vitest";
import { useSearchDraftStore } from "./searchDraftStore";

const initialState = useSearchDraftStore.getInitialState();

describe("useSearchDraftStore (§5.2/§11.2 in-progress Search & Settings edits)", () => {
  beforeEach(() => {
    useSearchDraftStore.setState(initialState, true);
  });

  it("defaults to an empty query, relevance sort, no read-aloud fields, not_interested default, speed 1", () => {
    const state = useSearchDraftStore.getState();
    expect(state.query).toBe("");
    expect(state.sort).toBe("relevance");
    expect(state.readAloudFields).toEqual([]);
    expect(state.defaultSwipeBehavior).toBe("not_interested");
    expect(state.speed).toBe(1);
  });

  it("setQuery/setSort/setSpeed/setDefaultSwipeBehavior update their single field", () => {
    useSearchDraftStore.getState().setQuery("spiking neural networks");
    useSearchDraftStore.getState().setSort("citations");
    useSearchDraftStore.getState().setSpeed(1.5);
    useSearchDraftStore.getState().setDefaultSwipeBehavior("interested");

    const state = useSearchDraftStore.getState();
    expect(state.query).toBe("spiking neural networks");
    expect(state.sort).toBe("citations");
    expect(state.speed).toBe(1.5);
    expect(state.defaultSwipeBehavior).toBe("interested");
  });

  it("toggleReadAloudField adds then removes a field (§3.2.C's subset selection)", () => {
    useSearchDraftStore.getState().toggleReadAloudField("journal");
    expect(useSearchDraftStore.getState().readAloudFields).toEqual(["journal"]);

    useSearchDraftStore.getState().toggleReadAloudField("last_author");
    expect(useSearchDraftStore.getState().readAloudFields).toEqual(["journal", "last_author"]);

    useSearchDraftStore.getState().toggleReadAloudField("journal");
    expect(useSearchDraftStore.getState().readAloudFields).toEqual(["last_author"]);
  });

  it("hydrate overwrites the whole draft at once, for §3.5's pre-fill", () => {
    useSearchDraftStore.getState().hydrate({
      query: "prior query",
      sort: "recency",
      readAloudFields: ["pub_date"],
      defaultSwipeBehavior: "interested",
      speed: 2,
    });

    const state = useSearchDraftStore.getState();
    expect(state.query).toBe("prior query");
    expect(state.sort).toBe("recency");
    expect(state.readAloudFields).toEqual(["pub_date"]);
    expect(state.defaultSwipeBehavior).toBe("interested");
    expect(state.speed).toBe(2);
  });
});
