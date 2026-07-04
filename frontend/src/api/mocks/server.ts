import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Node-side MSW server for Vitest tests (api/*.test.ts). */
export const server = setupServer(...handlers);
