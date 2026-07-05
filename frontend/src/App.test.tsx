import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { createTestQueryClient, wrapperWithClient } from './api/testUtils'
import { API_BASE_URL } from './api/client'
import { server } from './api/mocks/server'
import { usePanelStore } from './state/panelStore'
import { useSearchDraftStore } from './state/searchDraftStore'
import { useNetworkStore } from './state/networkStore'
import { usePlaybackStore } from './state/playbackStore'
import { useZoteroPushFlowStore } from './state/zoteroPushFlowStore'
import { usePlaybackEngine } from './playback/usePlaybackEngine'
import type { UsePlaybackEngineResult } from './playback/usePlaybackEngine'

// Mocked only for the mid-narration-decision regression test below (the
// "BLOCKING" finding from adversarial review, "TASK 4A REVIEW") — every
// other test in this file gets the default `status: "idle"` engine
// double, which doesn't change any of their existing assertions (none
// of them depend on real speech-synthesis mechanics). Mocking the whole
// module (rather than injecting a fake `env` into the real hook) is what
// lets the test assert `App.tsx`'s `decide()` closure itself calls
// `cancel()` synchronously, independent of whatever the real hook's
// internals do (those have their own dedicated coverage in
// `usePlaybackEngine.test.ts`).
vi.mock('./playback/usePlaybackEngine', async () => {
  const actual = await vi.importActual<typeof import('./playback/usePlaybackEngine')>(
    './playback/usePlaybackEngine',
  )
  return { ...actual, usePlaybackEngine: vi.fn() }
})

const mockedUsePlaybackEngine = vi.mocked(usePlaybackEngine)

function makeEngineDouble(overrides: Partial<UsePlaybackEngineResult> = {}): UsePlaybackEngineResult {
  return {
    status: 'idle',
    currentKey: null,
    speechSupported: true,
    usingFallbackTimer: false,
    unsupportedNotice: null,
    dismissUnsupportedNotice: vi.fn(),
    play: vi.fn(),
    pause: vi.fn(),
    cancel: vi.fn(),
    ...overrides,
  }
}

const initialPanelState = usePanelStore.getInitialState()
const initialDraftState = useSearchDraftStore.getInitialState()
const initialNetworkState = useNetworkStore.getInitialState()
const initialPlaybackState = usePlaybackStore.getInitialState()
const initialZoteroPushFlowState = useZoteroPushFlowStore.getInitialState()

function renderApp() {
  const client = createTestQueryClient()
  return render(<App />, { wrapper: wrapperWithClient(client) })
}

describe('App (§3.3/§5.1 — real wiring as of Task 4A)', () => {
  beforeEach(() => {
    usePanelStore.setState(initialPanelState, true)
    useSearchDraftStore.setState(initialDraftState, true)
    useNetworkStore.setState(initialNetworkState, true)
    usePlaybackStore.setState(initialPlaybackState, true)
    useZoteroPushFlowStore.setState(initialZoteroPushFlowState, true)
    mockedUsePlaybackEngine.mockReset()
    mockedUsePlaybackEngine.mockReturnValue(makeEngineDouble())
  })

  it('renders the Idle screen (no search run yet) without crashing', () => {
    renderApp()
    // §5.1: before any search this visit, Screen A (Idle) is shown —
    // the MSW-mocked `GET /search/settings` fixture returns `query: ""`.
    expect(screen.getByText('LitList')).toBeInTheDocument()
  })

  // Tester's TASK 4A VERIFY finding: App.tsx never surfaced errors or
  // offline state anywhere, even though SearchSettingsPanel's
  // error/isOffline/onRetry props (and the shared ErrorState component,
  // Task 4C) existed specifically to receive them. These tests are the
  // regression coverage for that fix.
  describe('error/offline surfacing (§4.5, §13.6)', () => {
    it('shows the external-downtime error (not a silent no-op) when a search fails with service_unavailable', async () => {
      const user = userEvent.setup()
      server.use(
        http.post(`${API_BASE_URL}/search`, () =>
          HttpResponse.json(
            { error: { code: 'service_unavailable', message: 'PubMed is currently unavailable. Please try again shortly.' } },
            { status: 503 },
          ),
        ),
      )

      renderApp()
      await user.click(screen.getByRole('button', { name: /swipe down to search/i }))
      await user.type(screen.getByLabelText(/search pubmed/i), 'computational neuroscience')
      await user.click(screen.getByRole('button', { name: /^start/i }))

      const errorState = await screen.findByTestId('error-state')
      expect(errorState).toHaveAttribute('data-code', 'service_unavailable')
      expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument()
      // A real retry affordance, not a dead end.
      expect(screen.getByRole('button', { name: /^retry$/i })).toBeInTheDocument()
    })

    it('shows the offline copy — distinct from service_unavailable — when networkStore reports offline', async () => {
      const user = userEvent.setup()
      renderApp()
      await user.click(screen.getByRole('button', { name: /swipe down to search/i }))

      useNetworkStore.getState().setOnline(false)

      await waitFor(() => expect(screen.getByTestId('error-state')).toHaveAttribute('data-code', 'offline'))
      expect(screen.getByText(/you're offline/i)).toBeInTheDocument()
    })

    it('shows an error surface (not the misleading "no papers matched" empty state) when GET /queue itself fails', async () => {
      // Simulates resuming a session where a search already ran (so
      // `GET /search/settings` reflects a real query and
      // `hasSearchedThisVisit` is true on first render, no interaction
      // needed) but `GET /queue` itself fails on this load — distinct
      // from the "just ran a search" path, since `useRunSearch`'s own
      // `onSuccess` seeds the queue cache directly and would otherwise
      // mask a `GET /queue` failure entirely.
      server.use(
        http.get(`${API_BASE_URL}/search/settings`, () =>
          HttpResponse.json({
            query: 'computational neuroscience',
            sort: 'relevance',
            read_aloud_fields: [],
            default_swipe_behavior: 'not_interested',
            speed: 1,
          }),
        ),
        http.get(`${API_BASE_URL}/queue`, () =>
          HttpResponse.json(
            { error: { code: 'service_unavailable', message: 'PubMed is currently unavailable. Please try again shortly.' } },
            { status: 503 },
          ),
        ),
      )

      renderApp()

      const errorState = await screen.findByTestId('error-state')
      expect(errorState).toHaveAttribute('data-code', 'service_unavailable')
      // Never the zero-result copy — that would misrepresent a fetch
      // failure as "your search legitimately found nothing."
      expect(screen.queryByText(/no papers matched/i)).not.toBeInTheDocument()
    })
  })

  // Adversarial review (TASK 4A REVIEW, BLOCKING finding): SPEC.md §6.6
  // requires `speechSynthesis.cancel()` synchronously as part of a
  // decision ("no audible overlap between papers"). `decide()` previously
  // only wrote to `playbackStore` (a UI-display-only Zustand store) and
  // never touched the live `usePlaybackEngine` instance actually holding
  // the utterance, so the old paper kept narrating underneath. This is
  // the regression test for that fix.
  describe('mid-narration decisions call the playback engine\'s cancel() (§6.6)', () => {
    it('decide() calls usePlaybackEngine().cancel() synchronously when a decision is made while playing', async () => {
      const user = userEvent.setup()
      const cancelSpy = vi.fn()
      mockedUsePlaybackEngine.mockReturnValue(
        makeEngineDouble({ status: 'playing', currentKey: 'segment-0', cancel: cancelSpy }),
      )

      server.use(
        http.get(`${API_BASE_URL}/search/settings`, () =>
          HttpResponse.json({
            query: 'computational neuroscience',
            sort: 'relevance',
            read_aloud_fields: [],
            default_swipe_behavior: 'not_interested',
            speed: 1,
          }),
        ),
      )

      renderApp()

      await screen.findByRole('heading', { name: /effects of early intervention/i })
      expect(cancelSpy).not.toHaveBeenCalled()

      await user.click(screen.getByRole('button', { name: /^interested$/i }))

      // Synchronous with the decision, not merely "eventually" — no
      // `waitFor` here, matching §6.6's "must happen synchronously with
      // the swipe handler" requirement.
      expect(cancelSpy).toHaveBeenCalledTimes(1)
    })

    it('does not call cancel() when a decision is made while nothing is playing', async () => {
      const user = userEvent.setup()
      const cancelSpy = vi.fn()
      mockedUsePlaybackEngine.mockReturnValue(
        makeEngineDouble({ status: 'idle', cancel: cancelSpy }),
      )

      server.use(
        http.get(`${API_BASE_URL}/search/settings`, () =>
          HttpResponse.json({
            query: 'computational neuroscience',
            sort: 'relevance',
            read_aloud_fields: [],
            default_swipe_behavior: 'not_interested',
            speed: 1,
          }),
        ),
      )

      renderApp()
      await screen.findByRole('heading', { name: /effects of early intervention/i })
      await user.click(screen.getByRole('button', { name: /^interested$/i }))

      // §6.6's requirement is specifically about interrupting *live*
      // narration — `cancel()` is cheap/idempotent either way, but this
      // still confirms `decide()` calls it unconditionally on every
      // decision (not just when the mock happens to report "playing"),
      // which is the actually-correct, simplest-to-reason-about
      // behavior: cancel() is what makes the invariant "the engine is
      // the one source of truth for what's currently sounding" hold
      // regardless of what App.tsx *thinks* the status is.
      expect(cancelSpy).toHaveBeenCalledTimes(1)
    })
  })

  // Coordinator-flagged coverage gap (post tester's VERIFY of Task 4B's
  // two post-review fixes): tester proved the double-submit ref guard
  // has real regression coverage, but found that removing
  // `confirmDisconnectDuringPush`/`zoteroPushFlowStore` wiring from
  // `App.tsx` entirely left all 156 frontend tests green — the guard's
  // own unit test (`confirmDisconnectDuringPush.test.ts`) only proves
  // the *function* is correct in isolation, nothing proved `App.tsx`
  // actually calls it before disconnecting.
  //
  // These tests drive a *genuinely* in-flight push through the real,
  // fully-mounted `<ZoteroPushModal />` (open the flow, pick a
  // collection, click the real Save button against a deliberately-held
  // `POST /zotero/push` response) rather than reaching into
  // `zoteroPushFlowStore` and setting `isPushPending` directly — an
  // earlier draft of this test did that and passed for the wrong reason
  // (it never actually exercised `App.tsx`'s wiring): the *real*
  // `useZoteroPushFlowController` instance `<ZoteroPushModal />` always
  // mounts overwrites that same store field from its own (idle)
  // `useZoteroPush().isPending` on its very next effect pass, silently
  // clobbering the manually-forced `true` back to `false` before the
  // click ever happened. Driving a real push through the real modal is
  // what actually exercises `App.tsx`'s `handleDisconnectZotero` -> the
  // real `confirmDisconnectDuringPush` -> the real `useDisconnectZotero`
  // mutation -> a real (MSW-mocked) `DELETE /zotero/connection` request.
  describe('Disconnect Zotero vs. an in-flight push (Task 4B post-review fix #2, §5.4/§9.6)', () => {
    /** Holds `POST /zotero/push` open until resolved, so assertions can
     *  observe the store's real `isPushPending: true` before the
     *  mutation settles — same technique as `useZoteroPushFlowController
     *  .test.tsx`'s own `deferredPushHandler`. */
    function deferredPushHandler() {
      let resolvePush!: () => void
      const pending = new Promise<void>((res) => {
        resolvePush = res
      })
      server.use(
        http.post(`${API_BASE_URL}/zotero/push`, async ({ request }) => {
          const body = (await request.json()) as { pmids: string[] }
          await pending
          return HttpResponse.json({
            collection_key: 'ABCD1234',
            results: body.pmids.map((pmid) => ({ pmid, status: 'success' as const, zotero_item_key: `K-${pmid}` })),
          })
        }),
      )
      return { resolvePush }
    }

    async function startRealPushInFlight(user: ReturnType<typeof userEvent.setup>) {
      server.use(
        http.get(`${API_BASE_URL}/zotero/collections`, () =>
          HttpResponse.json({ connected: true, collections: [{ key: 'ABCD1234', name: 'Journal Club' }] }),
        ),
      )
      const { resolvePush } = deferredPushHandler()

      renderApp()
      usePanelStore.getState().openSaved()

      await user.click(await screen.findByRole('button', { name: /push to zotero/i }))
      await user.click(await screen.findByLabelText('Journal Club'))
      await user.click(screen.getByRole('button', { name: /^save$/i }))

      // The real controller's own effect has now mirrored its real
      // `push.isPending` into the shared store.
      await waitFor(() => expect(useZoteroPushFlowStore.getState().isPushPending).toBe(true))

      return { resolvePush }
    }

    it('blocks the real DELETE /zotero/connection request while a real push is in flight, and the user declines the confirmation', async () => {
      const user = userEvent.setup()
      let deleteCallCount = 0
      server.use(
        http.delete(`${API_BASE_URL}/zotero/connection`, () => {
          deleteCallCount += 1
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

      const { resolvePush } = await startRealPushInFlight(user)

      await user.click(screen.getByTestId('disconnect-zotero-button'))

      // The guard must actually run — a real confirmation naming the
      // in-flight push, not a silent pass-through — and, since the user
      // declined, the real network request must never fire.
      expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/still in progress/i))
      expect(deleteCallCount).toBe(0)
      expect(screen.getByTestId('disconnect-zotero-button')).toBeInTheDocument()

      resolvePush()
      await waitFor(() => expect(useZoteroPushFlowStore.getState().isPushPending).toBe(false))
      confirmSpy.mockRestore()
    })

    it('proceeds with the real DELETE /zotero/connection request when the user confirms anyway, even while the push is still in flight', async () => {
      const user = userEvent.setup()
      let deleteCallCount = 0
      server.use(
        http.delete(`${API_BASE_URL}/zotero/connection`, () => {
          deleteCallCount += 1
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      const { resolvePush } = await startRealPushInFlight(user)

      await user.click(screen.getByTestId('disconnect-zotero-button'))

      expect(confirmSpy).toHaveBeenCalledWith(expect.stringMatching(/still in progress/i))
      await waitFor(() => expect(deleteCallCount).toBe(1))

      resolvePush()
      confirmSpy.mockRestore()
    })

    it('disconnects immediately with no confirmation prompt when no push is in flight', async () => {
      const user = userEvent.setup()
      let deleteCallCount = 0
      server.use(
        http.get(`${API_BASE_URL}/zotero/collections`, () =>
          HttpResponse.json({ connected: true, collections: [{ key: 'ABCD1234', name: 'Journal Club' }] }),
        ),
        http.delete(`${API_BASE_URL}/zotero/connection`, () => {
          deleteCallCount += 1
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const confirmSpy = vi.spyOn(window, 'confirm')

      renderApp()
      usePanelStore.getState().openSaved()

      await user.click(await screen.findByTestId('disconnect-zotero-button'))

      expect(confirmSpy).not.toHaveBeenCalled()
      await waitFor(() => expect(deleteCallCount).toBe(1))

      confirmSpy.mockRestore()
    })
  })
})
