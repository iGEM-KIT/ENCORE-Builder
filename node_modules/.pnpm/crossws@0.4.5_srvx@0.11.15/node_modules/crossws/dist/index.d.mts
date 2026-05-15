import { a as Hooks, c as Message, d as PeerContext, f as WSError, i as defineWebSocketAdapter, l as AdapterInternal, n as AdapterInstance, o as ResolveHooks, r as AdapterOptions, s as defineHooks, t as Adapter, u as Peer } from "./_chunks/adapter.mjs";
import { n as WSOptions, t as ServerWithWSOptions } from "./_chunks/_types.mjs";
interface WebSocketProxyOptions {
  /**
   * Target WebSocket URL to proxy to (`ws://` or `wss://`).
   *
   * Can be a static string/URL or a function that resolves the target dynamically
   * based on the incoming {@link Peer}.
   */
  target: string | URL | ((peer: Peer) => string | URL);
  /**
   * Forward the client's `sec-websocket-protocol` header to the upstream.
   *
   * @default true
   */
  forwardProtocol?: boolean;
  /**
   * Maximum number of bytes buffered per peer while the upstream connection
   * is still opening. If exceeded, the peer is closed with code `1009`
   * (Message Too Big). Set to `0` to disable the limit.
   *
   * @default 1048576 (1 MiB)
   */
  maxBufferSize?: number;
  /**
   * Milliseconds to wait for the upstream WebSocket handshake to complete.
   * If the upstream does not open within the timeout, the peer is closed
   * with code `1011`. Set to `0` to disable the timeout.
   *
   * @default 10000
   */
  connectTimeout?: number;
  /**
   * Custom `WebSocket` constructor used to dial the upstream. Useful when
   * the runtime does not expose a global `WebSocket` (Node.js < 22) or
   * when you want to use a different client implementation (e.g. `ws`,
   * `undici`, a mock for tests).
   *
   * @default globalThis.WebSocket
   */
  WebSocket?: typeof WebSocket;
  /**
   * Extra headers to send on the upstream handshake. Can be a static
   * object or a resolver called per peer.
   *
   * Useful to forward identity from the incoming request (`cookie`,
   * `authorization`, `origin`), or to inject a shared secret the
   * upstream expects.
   *
   * > [!NOTE]
   * > The WHATWG global `WebSocket` constructor does not accept custom
   * > headers — this option is only honored by `WebSocket` constructors
   * > that take a third options argument (e.g. `ws`, `undici`). Pass
   * > one via the {@link WebSocket} option to use it.
   *
   * @example
   * ```ts
   * createWebSocketProxy({
   *   target: "wss://backend.example.com",
   *   WebSocket: WsFromNodeWs,
   *   headers: (peer) => ({
   *     cookie: peer.request.headers.get("cookie") ?? "",
   *     "x-forwarded-for": peer.remoteAddress ?? "",
   *   }),
   * });
   * ```
   */
  headers?: HeadersInit | ((peer: Peer) => HeadersInit | undefined | void);
}
/**
 * Create a set of crossws hooks that proxy incoming WebSocket connections
 * to an upstream `ws://` or `wss://` target.
 *
 * @example
 * ```ts
 * import { createWebSocketProxy } from "crossws";
 *
 * const hooks = createWebSocketProxy("wss://echo.websocket.org");
 * ```
 */
declare function createWebSocketProxy(target: WebSocketProxyOptions["target"] | WebSocketProxyOptions): Partial<Hooks>;
export { type Adapter, type AdapterInstance, type AdapterInternal, type AdapterOptions, type Hooks, type Message, type Peer, type PeerContext, type ResolveHooks, type ServerWithWSOptions, type WSError, type WSOptions, type WebSocketProxyOptions, createWebSocketProxy, defineHooks, defineWebSocketAdapter };