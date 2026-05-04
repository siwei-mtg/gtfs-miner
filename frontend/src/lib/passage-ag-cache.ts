/**
 * passage-ag-cache.ts
 *
 * In-memory cache for `/map/passage-ag` GeoJSON responses.
 *
 *  - Keyed by `${projectId}|${queryString}` so different filter combinations
 *    coexist; the call site already serialises filters into `qs`.
 *  - Hits within `STALE_MS` are returned synchronously (no network round-trip).
 *  - Concurrent callers with the same key share the in-flight Promise — a
 *    rapid burst of filter changes triggers exactly one fetch.
 *
 * Stale-while-revalidate is intentionally NOT implemented: the backend now
 * has its own LRU+TTL cache, so a refetch is cheap. A simple "fresh if <60s
 * else refetch" semantics keeps the call site obvious and avoids double-render
 * race conditions in PassageAGLayer.
 */

const STALE_MS = 60_000;
const GC_MS = 5 * 60_000;
const MAX_ENTRIES = 32;

type CacheEntry = {
  timestamp: number;
  data: unknown;
  inflight?: Promise<unknown>;
};

const cache = new Map<string, CacheEntry>();

function gc(): void {
  const cutoff = Date.now() - GC_MS;
  for (const [key, entry] of cache) {
    if (entry.timestamp < cutoff && !entry.inflight) cache.delete(key);
  }
  while (cache.size > MAX_ENTRIES) {
    const oldestKey = cache.keys().next().value;
    if (oldestKey === undefined) break;
    cache.delete(oldestKey);
  }
}

export function invalidatePassageAGCache(projectId?: string): void {
  if (projectId === undefined) {
    cache.clear();
    return;
  }
  const prefix = `${projectId}|`;
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}

export async function fetchPassageAG<T = unknown>(
  url: string,
  cacheKey: string,
  token?: string | null,
  opts: { force?: boolean } = {},
): Promise<T> {
  const existing = cache.get(cacheKey);
  if (!opts.force && existing) {
    if (existing.inflight) return existing.inflight as Promise<T>;
    if (Date.now() - existing.timestamp < STALE_MS) return existing.data as T;
  }

  const inflight = (async () => {
    const response = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
    const data = (await response.json()) as T;
    cache.set(cacheKey, { timestamp: Date.now(), data });
    gc();
    return data;
  })();

  // Park the in-flight Promise so concurrent callers reuse it.
  cache.set(cacheKey, {
    timestamp: existing?.timestamp ?? 0,
    data: existing?.data,
    inflight,
  });

  try {
    return await inflight;
  } catch (err) {
    // Don't poison the cache with a failed fetch; drop the in-flight marker
    // so a retry can happen.
    const cur = cache.get(cacheKey);
    if (cur?.inflight === inflight) {
      if (cur.data !== undefined) {
        cache.set(cacheKey, { timestamp: cur.timestamp, data: cur.data });
      } else {
        cache.delete(cacheKey);
      }
    }
    throw err;
  }
}
