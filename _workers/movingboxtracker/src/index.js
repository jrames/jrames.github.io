const CANONICAL_HOST = "movingboxtracker.com";
const ORIGIN = "https://www.jefframes.com";
const ORIGIN_PREFIX = "/box-tracker";

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (url.hostname !== CANONICAL_HOST || url.protocol !== "https:") {
      url.hostname = CANONICAL_HOST;
      url.protocol = "https:";
      return Response.redirect(url.toString(), 301);
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
    }

    const upstream = new URL(ORIGIN_PREFIX + url.pathname + url.search, ORIGIN);
    const response = await fetch(upstream.toString(), {
      method: request.method,
      headers: forwardedHeaders(request.headers),
      redirect: "manual",
      cf: { cacheTtl: 300, cacheEverything: true },
    });

    // GitHub Pages redirects (e.g. adding a trailing slash) point at its own host; keep
    // visitors on this domain instead.
    const location = response.headers.get("Location");
    if (location) {
      return Response.redirect(rewriteLocation(location, url), response.status);
    }

    const headers = new Headers(response.headers);
    for (const name of ["Set-Cookie", "X-GitHub-Request-Id", "X-Served-By", "X-Fastly-Request-ID"]) {
      headers.delete(name);
    }
    return new Response(response.body, { status: response.status, headers });
  },
};

// Range is required for Safari to play the demo video; the conditional headers keep
// revalidation cheap.
const FORWARDED_HEADERS = ["Range", "If-None-Match", "If-Modified-Since", "Accept", "Accept-Encoding", "User-Agent"];

function forwardedHeaders(incoming) {
  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = incoming.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function rewriteLocation(location, requestURL) {
  const target = new URL(location, ORIGIN);
  const isOrigin = target.hostname.endsWith("jefframes.com") || target.hostname === "jrames.github.io";
  if (isOrigin && target.pathname.startsWith(ORIGIN_PREFIX)) {
    const path = target.pathname.slice(ORIGIN_PREFIX.length) || "/";
    return new URL(path + target.search, `https://${requestURL.hostname}`).toString();
  }
  return target.toString();
}
