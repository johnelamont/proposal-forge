# ADR-002: Mobile Strategy (Progressive Web App vs Native)

**Status:** Accepted  
**Date:** 2026-09-27  
**Deciders:** John Lamont

## Context

Proposal-forge must work on mobile (iPhone, Android) for:
- Browsing Upwork jobs on phone
- Pasting job posts into app
- Quick win/loss status checks
- Mobile copy-paste workflow

Need to choose: PWA (web-based, installable) or native app (iOS + Android).

## Options Considered

### Option A: Progressive Web App (Chosen)

| Dimension | Assessment |
|-----------|-----------|
| **Development time** | Low (one codebase: Next.js) |
| **Time to market** | Fast (deploy to Vercel, no app store review) |
| **Cost** | $0 (included in Next.js + Vercel) |
| **User experience** | 90% native-like (install to home screen, offline, push notifications possible) |
| **Team familiarity** | High (React/Next.js) |
| **Maintenance** | Single codebase (no iOS/Android divergence) |

**Pros:**
- One codebase → web + mobile with responsive design
- Install-to-home-screen looks like native app
- Service worker enables offline mode (service proposal drafts without internet)
- No app store submission (iterate freely)
- Zero cost
- Works across iOS, Android, desktop (same code)
- Easy to update (users get latest on reload, no app store delays)
- Can add push notifications later (Web Push API)

**Cons:**
- Not true native (no deep OS integration)
- Limited access to device hardware (camera, NFC, etc.)
- iOS PWA support lags Android (but improving)
- Users must know to "Add to Home Screen" (not automatic discovery)
- Offline mode limited to cached pages (not full app)

### Option B: Native Apps (iOS + Android)

| Dimension | Assessment |
|-----------|-----------|
| **Development time** | High (Swift + Kotlin, separate codebases) |
| **Time to market** | Slow (app store review, 1-2 weeks per update) |
| **Cost** | $100/year iOS Developer + infra |
| **User experience** | 100% native (full hardware access) |
| **Team familiarity** | Low (requires Swift/Kotlin skills) |
| **Maintenance** | High (OS updates, two codebases) |

**Pros:**
- True native experience (deep OS integration)
- Full access to device hardware (camera, contacts, notifications)
- Instant launch from home screen (no browser involvement)
- Easier to monetize (App Store in-app purchases)
- Discoverable through app stores
- Better offline experience (can cache entire app)

**Cons:**
- Two codebases (iOS + Android) → double maintenance
- App store review delays (1-2 weeks per release)
- Higher development cost ($100/year + dev time)
- Slower iteration (review delays)
- Not necessary for this use case (mainly paste/copy/edit)
- Users must download and install from store

### Option C: React Native (Hybrid)

| Dimension | Assessment |
|-----------|-----------|
| **Development time** | Medium (one codebase, but native module pain) |
| **Time to market** | Medium (app store needed, but code reuse helps) |
| **Cost** | $100/year iOS + EAS build tools |
| **UX** | Near-native (not quite 100%) |

**Pros:**
- One JavaScript codebase for iOS and Android
- Near-native performance

**Cons:**
- Still requires app store submission
- Not faster to market than PWA
- Adds complexity (native modules, OS-specific configs)
- Overkill for this use case (mostly CRUD + copy-paste)
- Harder to share with web users

## Trade-off Analysis

**User experience:**
- Native (B) = 100% native feel
- React Native (C) = 95% native feel
- PWA (A) = 85% native feel → sufficient for proposal drafting

**Time to market:**
- PWA (A) wins. Deploy today, no gatekeepers.
- React Native (C) 2-3 weeks (build, review cycle).
- Native (B) 4-6 weeks (separate platforms).

**Cost:**
- PWA (A) = $0
- React Native (C) = $100/year
- Native (B) = $100/year + 2-3x dev time

**Maintenance:**
- PWA (A) wins. Single codebase.
- React Native (C) = one codebase, multiple OS targets (complexity)
- Native (B) = two codebases, OS-specific bugs, drift.

**Suitability for this use case:**
- Proposal-forge is primarily: paste input, edit text, copy output
- No hardware integration needed (no camera, sensors, bluetooth)
- No deep OS notifications needed
- Mobile offline mode helpful but not critical

**Portfolio value:**
- PWA (A) shows you can build installable web apps (modern skill)
- React Native (C) shows you can do cross-platform mobile
- Native (B) not a differentiator (everyone can hire native devs)

## Decision

**Use Progressive Web App (Option A).**

- Zero cost
- Single Next.js codebase (web + mobile)
- Fast iteration (no app store delays)
- 90% of native experience for this use case
- Modern, relevant to GitHub portfolio
- Easy offline support (service worker)
- Responsive design handles all screen sizes

Mobile users will:
1. Visit app in browser on phone
2. See "Add to Home Screen" prompt (iOS/Android)
3. Tap → app installs like native app
4. Launches full-screen, no browser chrome
5. Works offline for cached pages

## Consequences

**What becomes easier:**
- Iteration (no review gates)
- Testing (web dev tools same everywhere)
- User feedback loop (push update, users see it next load)
- Sharing (send link, no app store discovery lag)
- Analytics (standard web analytics tools)

**What becomes harder:**
- Deep hardware integration (would require web APIs, fallbacks)
- Real-time notifications (push notifications possible but not automatic)
- App store discoverability (no app store presence)

**What we'll need to mitigate:**
- iOS PWA support is improving but still behind Android
  - Mitigation: Test on both, document limitations, provide browser fallback
- User awareness of "Add to Home Screen"
  - Mitigation: In-app prompt, clear help docs
- Offline mode limited to cached pages
  - Mitigation: Service worker caches most-used flows, graceful degradation for others

## Related Decisions

- ADR-001: Backend choice affects PWA (need JSON API, not server-side rendering) ✓ FastAPI provides this
- Mobile UX: Copy-to-clipboard buttons, large touch targets, no horizontal scroll (UI requirements, not architectural)
