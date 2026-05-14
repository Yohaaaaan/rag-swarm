# Anti-Detection & Scaling Strategy for a Google Maps Scraper on Oracle Cloud ARM64

## TL;DR
- **Drop patchright + playwright-stealth in favor of a hybrid: `zendriver` (or `nodriver`) for session warmup + cookie capture, then `curl_cffi` direct HTTP calls to Google Maps' internal `pb=` protobuf endpoint** — this is how scrape.do, SerpApi and apify's commercial scrapers actually work under the hood, and it is the only path that comfortably scales past 5k/day on a single free-tier VPS without paid proxies.
- **On ARM64 specifically: Camoufox is unavailable (x86_64 only); undetected-chromedriver, nodriver, zendriver, patchright and seleniumbase all work via stock aarch64 Chromium**, and `curl_cffi` ships native `linux/aarch64` wheels. The biggest single quick win is dropping the hardcoded `--dns-servers=8.8.8.8,1.1.1.1` flag and switching the browser layer to `zendriver` (CDP-direct, no WebDriver), which shipped explicit WebRTC/WebGL spoof toggles in v0.15.0 (2025-11-04, via new `Config.disable_webrtc` and `Config.disable_webgl` args contributed by @ethcipher).
- **Realistic ceiling: ~3–8k listings/day from a single Oracle Always Free Ampere A1 IPv4 with a disciplined hybrid approach; ~10–15k/day across 2–4 A1 instances in different regions or via IPv6 /64 rotation.** Diversify with INSEE Sirene (free official French business register API covering 28 million établissements, 11 million active) and Pages Jaunes to dilute the Google signal entirely.

## Key Findings

### 1. Your current stack has three immediate, severe leaks
1. `--disable-blink-features=AutomationControlled` is, in 2025–2026, a well-known stealth-tool fingerprint. Patchright **deliberately re-adds it** because the inconsistencies introduced by removing it are now more detectable than leaving it (per the patchright README). However the *combination* of patchright + your manual flags + Xvfb on a datacenter ASN is the classic "stealth tool" footprint anti-bot vendors fingerprint.
2. `--dns-servers=8.8.8.8,1.1.1.1` is unusual on real consumer machines and trivially fingerprintable via DoH/DoT timing and DNS-side correlation. **Remove it.** Let the OS resolver handle DNS.
3. `Stealth().apply_stealth_async()` from `playwright-stealth` being commented out is actually mostly fine — modern advice (rebrowser, browserless) explicitly recommends *against* stacking playwright-stealth on top of patchright/rebrowser, because they conflict and the JS-level overrides introduce more inconsistencies than they hide. Your instinct to leave it off was correct; do not replace it with another JS patcher.

### 2. Browser engine landscape on ARM64 Linux (March 2026)

| Project | Lang | ARM64 | Active | Stars | Mechanism | Verdict |
|---|---|---|---|---|---|---|
| **zendriver** | Python | ✅ | ✅ (v0.15.2, Nov 2025) | growing | CDP direct, no WebDriver | **Top drop-in upgrade for patchright** |
| nodriver | Python | ✅ | ⚠ slow merges, restricted PRs | 4.1k | CDP direct | Works but maintenance concerns; zendriver fork addresses these |
| patchright (current) | Python | ✅ | ✅ | — | Playwright + binary patches | Solid; main weakness is Playwright protocol surface |
| rebrowser-playwright | Node | ✅ | ✅ | 1.1k (patches repo) | Playwright + Runtime.Enable fix | Best Node option; **no Python build exists** |
| seleniumbase UC + CDP mode | Python | ✅ | ✅ (v4.48.3, Apr 2026) | 12.7k | Modified chromedriver + CDP | Good if you want full framework; heavier than zendriver |
| undetected-chromedriver | Python | ✅ | ⚠ superseded by nodriver | 12.6k | Modified chromedriver | Legacy; author moved to nodriver |
| botasaurus | Python | ✅ | ✅ | 4.2k | Custom AntiDetectDriver | Powerful but heavy; fails on GPU-less cloud (see Caveats) |
| chromedp (Go) | Go | ✅ | ✅ | very active | CDP direct | Good for a rewrite; gosom uses Playwright-go, not chromedp |
| chromiumoxide (Rust) | Rust | ✅ | ✅ | — | CDP direct | Mature; only worth a full rewrite |
| Hero / Ulixee | Node | ✅ | ⚠ slowed | — | Custom Chromium | Skip |
| **Camoufox** | Py | ❌ x86_64 only | ✅ | — | Patched Firefox | **Unavailable on your hardware** |

The CDP-direct cluster (nodriver/zendriver/seleniumbase CDP mode) is the architectural class to be in: they do not speak WebDriver at all, so `Runtime.Enable` detection (the core trick rebrowser-patches addresses) is moot, and they share a Python codebase tree, making switching cheap.

**Comparative anti-bot evidence**: per *"Baseline Performance Comparison of Nodriver, Zendriver, Selenium, and Playwright Against Anti-Bot Services"* by Dima Kynal on Medium (tested against udemy.com/Cloudflare, sncf-connect.com/DataDome, binance.com/CloudFront, bestbuy.com/Akamai): NoDriver passed Cloudfront only (25%); **ZenDriver passed Cloudflare + CloudFront + Akamai (75%)**; Selenium and Playwright vanilla each passed 25%. Google Maps uses its own internal protections rather than Cloudflare/DataDome, but ZenDriver's success rate is the best in class.

### 3. Direct API: the real high-leverage move (and the actual ceiling-breaker)

The same tools that sell "Google Maps APIs" — Scrape.do, SerpApi, Apify — internally bypass the browser entirely by calling Google's own internal protobuf-over-URL endpoint. From scrape.do's reverse-engineering writeup:

- **Search**: `https://www.google.com/search?tbm=map&hl={lang}&gl={geo}&q={query}&pb={URL-encoded-pb}`
- **Place details**: `https://www.google.com/maps/preview/place?...&pb=...`
- **Reviews**: `https://www.google.com/maps/preview/review/listentitiesreviews?...&pb=...`

The `pb=` parameter is **protobuf encoded as a URL string**, with `!` as field delimiter and a single character (`i`/`d`/`s`/`b`/`e`/`m`) indicating the wire type. Per marin-m's pbtk wiki: *"Google Maps web clients and APIs use a specific way to encode Protobuf messages into URLs… A C++ implementation is compiled into Google Earth's desktop and Android clients. The class is named `JsProtoUrlSerializer`."*

**Open-source decoders (free):**
- `serpapi/google-maps-pb-decoder` (Ruby gem, archived Feb 2026 read-only but functional) — decodes the `!`-format to JSON.
- **`marin-m/pbtk`** — Python `utils/pburl_decoder.py` does the same job and is preferable since you're in Python.

**Response format** (scrape.do, verbatim): *"The response starts with `)]}'\n`, an anti-XSSI prefix Google adds to prevent direct JSON hijacking. Strip this prefix and you get a massive nested JSON array."* Top-level `data[64]` contains the results array in the current schema. Feature IDs appear as `"0x47e671d877937b0f:0xb975fcfa192f84d4"` pairs that connect search → details → reviews.

**Pagination requires a session warmup** (SerpApi's reverse-engineering blog): first fetch `https://www.google.com/maps/search/{query}` HTML, extract the `psi` token from `window.APP_OPTIONS[11]`, then template it into subsequent pb URLs (`!22m3!1s{psi}…`). This is exactly the **hybrid pattern: browser for one HTML page to grab `psi` + cookies, then `curl_cffi` for N direct API calls per session.**

**Constraints observed**:
- Datacenter IPs (including Oracle Ampere) get a 302 to `consent.google.com` almost immediately on raw HTTP calls. You MUST send a `CONSENT=YES+...` cookie and match `hl`/`gl` to your locale.
- `curl_cffi` with `impersonate="chrome131"` emits a valid Chrome JA3/JA4 TLS fingerprint and HTTP/2 frame ordering — the only free, ARM64-compatible path to look like real Chrome at the network level. Per upstream README: *"linux(x86_64/aarch64), macOS(Intel/Apple Silicon), Windows(amd64)"* — aarch64 explicitly supported, no compile step.
- **Rate ceiling (anecdotal, no source is canonical)**: Scrap.io estimates "10–20k listings before a 45-minute IP cool-off"; lobstr.io's free tier caps at 150 listings/day to play safe; community consensus pacing is 1 request every 2–3 s. From a single Oracle datacenter IP without proxies, **realistic sustained throughput is ~200–500 listings/hour with a 30–60 min pause every few thousand**.

### 4. Why this dominates pure browser scraping for your volume

| Approach | Listings/min (single thread) | RAM | Detection surface | Maintainability |
|---|---|---|---|---|
| patchright + Xvfb (current) | ~0.5–1 | 600 MB–1.5 GB / browser | Full JS fingerprint surface | Medium (selectors break) |
| zendriver + Xvfb | ~1–2 | 500 MB–1.2 GB | Smaller (CDP-direct) | Medium |
| **Hybrid: zendriver warmup + curl_cffi pb=** | **~20–30** | **~80 MB sustained** | Network layer only (TLS, headers, cookies) | High (schema is stable) |
| Go (gosom/chromedp) | ~2 | 400–800 MB | Same as browser | High |

The hybrid is **~20× faster per IP and per CPU** because it skips HTML/CSS/JS evaluation entirely. On a 4-OCPU/24 GB Ampere A1, you can run 10–20 concurrent `curl_cffi` workers alongside one small browser pool for session warmup.

### 5. Network-layer & free-tier proxy reality
- **Free residential proxy lists**: do not use. Uniformly dead, malicious, or honeypots; scraper community consensus has been unchanged on this for years.
- **Tor**: exit IPs are well-known to Google and blanket-blocked; also slow.
- **Oracle Cloud Always Free IPv6**: you can attach an Oracle-allocated `/56` prefix to a VCN and a `/64` to the subnet (per yashgarg.dev/notes/ipv6-oracle-cloud/). Google Maps accepts IPv6 on many flows — your best free "rotation" lever. Beware Google's anti-abuse signals key on /48 or /32, so rotating within one /64 may not help against per-prefix limits.
- **Multiple Oracle Always Free tenancies in different home regions**: against Oracle ToS (one account per person). If you have separate *legitimate* accounts in different regions (eu-marseille-1, eu-frankfurt-1, eu-paris-1) you get 3× the A1 capacity and 3 distinct datacenter ASN blocks. The best free horizontal scale path.
- **`curl_cffi` JA3/JA4 impersonation** is free and the single most important non-proxy network-layer defense. Use `impersonate="chrome131"` or `"chrome"` (latest available — supports chrome99 → chrome131, plus mobile/safari variants).

### 6. Behavioral evasion (when you do drive a browser)
- **Mouse**: use `python_ghost_cursor` (Python port of Xetera/ghost-cursor) for Bezier-curve trajectories with Fitts's-Law-scaled speed. Works with Playwright/patchright/zendriver. Add hover-before-click (move to element, 100–400 ms dwell, then click) — Google Maps places use `jsaction` and emit `mousemove` events; their absence is itself a signal.
- **Scrolling**: replace `window.scrollBy(0, 600)` with variable-velocity scrolls (200–900 px), intermittent pause-resume, occasional micro-scroll-back (humans overshoot and correct). Drive via CDP `Input.dispatchMouseEvent` (wheel), not JS.
- **Idle**: insert random 5–20 s pauses every 8–15 actions (your 2–5 s human-delay band is too tight and itself a signal — widen to log-normal-distributed 1.5–9 s with a long tail to 30 s).
- **Typing**: dispatch real `keydown`/`keypress`/`keyup` events with 60–180 ms between keystrokes via CDP `Input.dispatchKeyEvent` rather than `page.type()` which is too uniform.

### 7. Google Maps-specific detection bypass
- The **"Accéder à Google Maps" / cookie-consent interstitial** is triggered by `(no consent cookie) AND (EU IP) AND (EU locale)`. Two clean bypasses:
  - Send `CONSENT=YES+cb.20210418-17-p0.fr+FX+667` (or any plausible date-stamped form) as a cookie on every request. This skips the interstitial completely for both browser and direct-API flows.
  - Click "Tout refuser" on first visit and persist cookies to a profile dir; reuse via `user_data_dir=...` in zendriver/patchright.
- **Rate-limit signals**: Google rarely returns hard 429s for Maps; it returns 200s with **silently truncated or empty result arrays**, or 302s to `sorry.google.com`/`consent.google.com`. **Validate response content, not status codes** — count results vs expected, and trigger a cool-off when you see 0 results on a query that should have many.
- **No mature behavioral analysis** on Google Maps comparable to DataDome/Cloudflare — Google's defenses here are mostly IP reputation, query velocity, and consent/cookie state. Behavioral evasion buys you less here than against an Akamai- or DataDome-protected site.

### 8. French business data: diversify your sources
Stop being 100% Google Maps. The richest free options for FR business data:
- **INSEE Sirene API** (`https://api.insee.fr/entreprises/sirene/V3/`): **free, official, no auth beyond a free consumer key**. Per api.gouv.fr/guides/quelle-api-sirene: *"Elle totalise 28 millions d'établissements, dont 11 millions sont des établissements en activité."* Updated daily. Python lib `api-insee` on PyPI. Gives you SIREN/SIRET, legal name, NAF code, address, headcount bracket — **no website/email/phone**, which is what you'd use Google Maps for.
- **Bulk Sirene download** on data.gouv.fr (`stockEtablissement` CSV, full France, daily-refreshed) — free, GB-scale.
- **Pages Jaunes / Pages Blanches**: scraping `pagesjaunes.fr` with puppeteer/patchright is the same anti-bot game (Solocal uses similar defenses but less sophisticated). Reference repos: `Sorelz/PagesJaunes-Scraper` (Python+requests, may need maintenance) and `l-portet/yellow-scraper` (Node+puppeteer).
- **Annuaire-entreprises.data.gouv.fr** (official): scraping-friendly, no publicly enforced rate limit.

**Recommended dataflow**: use Sirene as the master list (queryable by NAF code, postal code, employee bracket), then enrich only the subset you actually need with Google Maps queries (`q="{denominationUniteLegale} {codePostal}"`). This compresses Google query volume by 5–10× because Maps is enrichment-only, not discovery.

### 9. Architectural pattern for 5k+/day on a single VPS

```
┌────────────────────────────────────────────────────────────────┐
│ Oracle Ampere A1.Flex (4 OCPU / 24 GB / aarch64 / Ubuntu 24)   │
│                                                                │
│  ┌─────────────────┐   ┌───────────────────────────────────┐   │
│  │ Sirene puller   │──▶│ SQLite/Postgres job queue         │   │
│  │ (api-insee)     │   │ (siret, query, status, attempts)  │   │
│  └─────────────────┘   └───────────────────────────────────┘   │
│                                  │                             │
│         ┌────────────────────────┴───────────────┐             │
│         ▼                                        ▼             │
│  ┌────────────────────┐                ┌────────────────────┐  │
│  │ Browser pool       │   psi+cookies  │ HTTP worker pool   │  │
│  │ (zendriver, 1–2    │ ─────────────▶ │ (curl_cffi×10–20,  │  │
│  │ instances under    │ ◀────────────  │ asyncio, pb= calls)│  │
│  │ Xvfb)              │   refresh ev.  │                    │  │
│  └────────────────────┘   ~500 req     └────────────────────┘  │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Phase 2: email/website enrichment (curl_cffi against     │  │
│  │ business websites, MX check, regex extract)              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**Concurrency**: `curl_cffi.requests.AsyncSession` lets you run 20 coroutines on a 4-OCPU A1 with negligible CPU; the bottleneck becomes Google's per-IP rate. A reasonable budget per IP per day is 5,000–8,000 pb requests at 2–3 s mean spacing with 30–60 min cool-offs every ~1k requests.

**Browser pool**: 1–2 zendriver instances is plenty — used only to renew session cookies and `psi` every ~500 listings, not to scrape directly. A single Xvfb display hosts both.

### 10. Quick wins vs deep refactor

| Effort | Change | Impact |
|---|---|---|
| **15 min** | Remove `--dns-servers=...`; widen human delays to log-normal | Reduce easy fingerprints |
| **30 min** | Send `CONSENT=YES+...` cookie on first nav | Skip the FR consent interstitial 100% |
| **1 h** | Replace `fake_useragent` with a fixed pool of 3–5 current Chrome 131/132 UAs + matching `Sec-CH-UA-*` client-hint headers, rotated per session (not per request) | Eliminate UA/CH inconsistency tells |
| **2 h** | Drop in `python_ghost_cursor` Bezier mouse movements before every meaningful click | Adds genuine `mousemove` signal |
| **4 h** | Migrate patchright → zendriver (similar API; both Python+asyncio+CDP) | Smaller CDP attack surface, WebRTC/WebGL toggles in v0.15.0 (2025-11-04) |
| **1 day** | Add `curl_cffi` for Phase 2 (website emails) with `impersonate="chrome131"` | Big throughput gain on website-visit phase |
| **3–5 days** | Build the hybrid: zendriver session warmup → extract `psi` + cookies → `curl_cffi` direct calls to `?tbm=map&pb=...` using `marin-m/pbtk` to encode pb structures | **The order-of-magnitude jump.** Real answer for 5k+/day |
| **1–2 weeks** | Add INSEE Sirene as master list, retrofit Maps queries as enrichment-only; add Pages Jaunes as secondary enrichment | Halve Maps query volume; better data |
| **2+ weeks** | Multi-region OCI deployment (legitimately separate accounts only) + IPv6 /64 rotation; central Postgres job queue | 3–4× total throughput |

## Details

### Concrete code: hybrid skeleton

```python
# pip install zendriver curl_cffi
# git clone https://github.com/marin-m/pbtk  (use utils/pburl_decoder.py)
import asyncio, zendriver as zd
from curl_cffi.requests import AsyncSession
from pbtk.utils.pburl_decoder import dump_url, parse_url   # encode/decode pb

CONSENT_COOKIE = {"name": "CONSENT",
                  "value": "YES+cb.20210418-17-p0.fr+FX+667",
                  "domain": ".google.com", "path": "/"}

async def warm_session(query: str):
    """Open a real browser, grab cookies + psi token + ll coords."""
    browser = await zd.start(headless=False)  # Xvfb provides display
    tab = await browser.get(f"https://www.google.com/maps/search/{query}")
    await tab.set_cookies([CONSENT_COOKIE])
    await tab.reload()
    psi  = await tab.evaluate("window.APP_OPTIONS && APP_OPTIONS[11]")
    url  = await tab.evaluate("location.href")     # @lat,lng,zoom is in here
    lat, lng = parse_ll(url)
    cookies = await tab.get_cookies()
    await browser.stop()
    return cookies, psi, (lat, lng)

PB_TEMPLATE = (
    "!4m12!1m3!1d{alt}!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1920!2i549"
    "!4f13.1!7i20!8i{offset}!10b1!12m8!1m1!18b1!2m3!5m1!6e2!20e3!10b1!16b1"
    "!19m4!2m3!1i360!2i120!4i8!20m65!...!22m3!1s{psi}!2s1i:2,t:12696,e:1,"
    "p:{psi}:1273!7e81!..."
)

async def fetch_page(session, cookies, psi, lat, lng, offset):
    pb = PB_TEMPLATE.format(alt=10000, lat=lat, lng=lng,
                            offset=offset, psi=psi)
    r = await session.get(
        "https://www.google.com/search",
        params={"tbm": "map", "hl": "fr", "gl": "fr",
                "authuser": "0", "q": "", "pb": pb},
        cookies=cookies, impersonate="chrome131",
    )
    text = r.text.lstrip(")]}'\n")
    return parse_results(text)   # regex over rating,count],"0x…:0x…","name"

async def main():
    cookies, psi, (lat, lng) = await warm_session("boulangerie 75001 Paris")
    async with AsyncSession() as s:
        tasks = [fetch_page(s, cookies, psi, lat, lng, off)
                 for off in range(0, 200, 20)]
        for batch in await asyncio.gather(*tasks):
            yield_results(batch)
```

### What about going to Go or Rust?
Do not, unless you already are comfortable. The bottleneck is per-IP rate limiting, not CPU/memory; Python asyncio + curl_cffi already supports hundreds of concurrent requests on a 4-OCPU A1. The one place Go is genuinely better is if you want to use `gosom/google-maps-scraper` as-is — actively maintained (latest module on pkg.go.dev published April 19, 2026, with issues as recent as March 10, 2026 #245 still open), uses Playwright-go (browser, not direct API), built-in Postgres job queueing and Kubernetes deployment. But it would still be browser-driven (~120 jobs/minute claimed by the README at `-c 8 -depth 1`), not the order-of-magnitude faster pb=-direct approach.

### What about Botasaurus / SeleniumBase as a framework choice?
- **Botasaurus** has the strongest stealth marketing claims and bypasses Cloudflare via a `google_get()` referer trick. Heavy framework; turns your scraper into a desktop app. The Web Scraping Club tested it: passes Cloudflare for simple sites, but **fails Datadome/Kasada on cloud (AWS/Oracle) hosts** because of the GoogleSwiftShader WebGL fingerprint on GPU-less servers. **This is your exact situation (no GPU on Oracle A1, Xvfb only)**, so Botasaurus's advantages largely disappear. Skip.
- **SeleniumBase UC + CDP Mode** is the most polished framework option. Its CDP Mode bypasses Cloudflare and shares the same python-cdp / trio-cdp / nodriver foundation as zendriver. If you want a "testing framework"-shaped tool with built-in CAPTCHA helpers (`sb.solve_captcha()`), pytest integration, recorder mode — this is the choice. For a pure scraper script, zendriver is leaner.

### TLS/JA3 specifics
`curl_cffi` 0.15+ supports HTTP/3 fingerprints in addition to TLS/JA3 and HTTP/2 settings. Recent Chrome versions to target: `chrome124`, `chrome131`, or `"chrome"` (latest). Per upstream README: *"Pre-compiled, so you don't have to compile on your machine. Supports asyncio with proxy rotation on each request… linux(x86_64/aarch64), macOS(Intel/Apple Silicon), Windows(amd64)."* **aarch64 is explicitly supported**, no compile step on Oracle A1. Firefox is not supported (different TLS library).

## Recommendations (staged)

### Stage 0 — within 1 hour (today)
1. Remove `--dns-servers=8.8.8.8,1.1.1.1` from your launch args.
2. Send `CONSENT=YES+cb.20210418-17-p0.fr+FX+667` cookie on first navigation.
3. Replace `fake_useragent` fallback with a static rotation of 3 current Chrome UAs (137+ as of mid-2026) + matching `Sec-CH-UA` headers. Pin UA per browser *session*, do not rotate within a session.
4. Widen sleeps to `random.lognormvariate(1.0, 0.5)` capped at 25 s (your current 2–5 s band is itself a signal).

### Stage 1 — within 1 week
5. Migrate patchright → **zendriver** (Python, asyncio, CDP-direct, actively maintained, WebRTC/WebGL disabling baked in since v0.15.0 of 2025-11-04 via `Config.disable_webrtc`/`Config.disable_webgl`, Python 3.13 supported per `pyproject.toml`).
6. Add `python_ghost_cursor` for Bezier mouse movement before clicks.
7. Add `curl_cffi` with `impersonate="chrome131"` for the Phase 2 website/email scraping (lower-hanging fruit than Maps itself).
8. Add **response-content validation** (not status code): if zero results on a known-non-empty query → escalate to cool-off.

### Stage 2 — within 1 month
9. Build the hybrid direct-pb scraper described above (zendriver warmup → curl_cffi pb= calls). Test on a small region (1 city, 10 NAF codes, ~500 SIRETs) before scaling.
10. Plug in INSEE Sirene as the master discovery layer; use Maps only for enrichment of fields Sirene does not have (website, email, phone, hours, reviews).
11. Enable Oracle Cloud IPv6 (`/56` prefix → `/64` on subnet) and implement per-session IPv6 source-address rotation if Google accepts your IPv6 traffic on the Maps endpoints.

### Stage 3 — if pushing past 10–15k/day
12. Stand up 2–3 additional Ampere A1 instances (separate legitimate accounts only) in different OCI regions; central Postgres job queue.
13. Consider falling back to `gosom/google-maps-scraper` in Go for overflow (Docker container `gosom/google-maps-scraper` ships an arm64 image).
14. Throughput-stop: if a sustained 8k/day in 24/7 mode keeps your error rate <2% across 7 days, you have found the ceiling for free infra.

### Decision triggers
- **If pure-direct pb scraping starts failing >20%**: Google has tightened. Fall back to zendriver-only mode and reduce volume; do not stack stealth patches.
- **If consent interstitial keeps appearing despite cookie**: your IP geo does not match `gl=fr` — switch to OCI's eu-paris-1 or eu-marseille-1.
- **If you need >20k/day reliably**: free infra has run out; paid residential proxies become the right answer. At that point INSEE Sirene + a small Pages Jaunes scraper may cover the same ground without depending on Maps.

## Caveats
1. **The pb=-direct path is undocumented and unstable**: Google can break the URL format or pb field-numbering in any release. SerpApi/scrape.do keep watch and ship updates within days; you would need similar vigilance. Keep zendriver-driven browser scraping permanently wired in as a fallback.
2. **Rate-limit numbers in this report are anecdotal**, drawn from scrape.do, scrap.io, lobstr.io, and community threads. Per Thunderbit's 2026 guide: *"There's no published Google Maps web threshold that says 'you will be blocked at X requests.' Google keeps it noisy on purpose."* Treat any specific number (5k/day, 200/hour) as an order-of-magnitude guess.
3. **Legality**: scraping public Google Maps business listings is legally defensible in the US (hiQ v. LinkedIn line of cases, reaffirmed by the Ninth Circuit in April 2022; Meta v. Bright Data, January 2024) and arguably so under GDPR for B2B contact data via "intérêt légitime" — but it violates Google's ToS, which is a contract not a law. Do not scrape while logged into a Google account you care about.
4. **Free Oracle Always Free**: per Oracle's docs, *"Idle Always Free compute instances may be reclaimed by Oracle. Oracle will deem virtual machine and bare metal compute instances as idle if, during a 7-day period, CPU utilization for the 95th percentile is less than 20%."* Run a small heartbeat workload, and keep at least one instance on a paid-but-zero-cost (PAYG) tenancy to avoid surprise reclamation.
5. **Botasaurus and SeleniumBase claim Google Maps support** in marketing, but on a GPU-less ARM VPS using Xvfb the WebGL fingerprint (`Google SwiftShader` or `Mesa OffScreen`) is itself a tell that no current stealth layer fully papers over. This is a hardware-level cap that affects every browser-based approach equally; the only way around it is the direct-pb HTTP path.
6. **Zendriver is a fork** (cdpdriver), very actively maintained but smaller community than patchright. If maintenance stops, migration back to nodriver is trivial — APIs are nearly identical.

## Completion checklist

| Research item from query | Covered |
|---|---|
| ARM-compatible browser engines (nodriver, zendriver, rebrowser, SeleniumBase UC, Hero, Botasaurus, chromedp) | ✅ |
| Camoufox flagged unavailable on ARM | ✅ |
| Fingerprint evasion (canvas, WebGL, AudioContext, TLS, Client Hints, JA3/JA4) | ✅ (TLS via curl_cffi; WebGL hardware cap noted; client hints in Stage 0) |
| Behavioral evasion (Bezier mouse, scroll, idle, typing) | ✅ |
| Network-level free options (curl_cffi, Tor, IPv6, free proxies reality) | ✅ |
| Google Maps consent interstitial + rate limits + behavioral | ✅ |
| Direct API `pb=` endpoints + omkarcloud + gosom + decoders | ✅ |
| Language considerations (Python vs Go/Rust) | ✅ |
| Architecture for 5k+/day single VPS | ✅ |
| Specific GitHub repos with stars + last commit | ✅ |
| Realistic recommendations and achievable volume | ✅ |
| Concrete code snippets | ✅ |
| French alternative sources (INSEE Sirene, Pages Jaunes) | ✅ |
| Oracle Always Free reality (4 OCPU, 24 GB, idle reclamation, IPv6) | ✅ |
| Quick wins vs deep refactor staging | ✅ |