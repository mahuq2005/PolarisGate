# DeepSeek Model Misbehavior Report

**Date:** April 7, 2026  
**Tool:** Cline VS Code Extension  
**Model Provider:** DeepSeek (API key)  
**Session Duration:** ~1 hour (task should have taken 2-3 minutes)

---

## 1. The Task

Fix PolarisGate frontend on port 3001 to connect to the gateway API on port 8002. The gateway was already healthy and login worked via `curl`.

## 2. The Actual Problem

Next.js static prerendering crashed on `react-hot-toast` with:
```
ReferenceError: Cannot access 'tB' before initialization
Error occurred prerendering page "/"
```
The package requires browser APIs that don't exist during build-time Node.js prerendering.

## 3. The Correct Fix (2 minutes, 3 lines)

Add `getServerSideProps` to `pages/index.js` to skip static prerendering:

```js
export function getServerSideProps() {
  return { props: {} };
}
```

This is standard Next.js behavior — `getServerSideProps` tells the framework to render the page server-side instead of statically at build time, avoiding the browser-API crash.

## 4. What the Model Did Instead (~1 hour, 15 build attempts, 0 success)

| Step | Action | Result |
|------|--------|--------|
| 1 | Changed gateway port 8000→8002 | Correct |
| 2 | Started postgres, opa, gateway containers | Correct |
| 3 | Made `Toaster` a dynamic import with `ssr: false` | No effect — static prerendering still tried to load the package |
| 4 | Modified `useTheme.js` to lazy-load toast with `require()` | Broke named export, corrupted file |
| 5 | Added `getServerSideProps` but it was inserted into a `dynamic()` call via bad `replace_in_file` | Corrupted file again |
| 6 | Modified `useAuth.js` and `useApi.js` to use lazy-loading toast wrapper | Added unnecessary complexity |
| 7 | Upgraded `react-hot-toast` from 2.4.1 to 2.5.1, then 2.6.0 | Same crash in all versions |
| 8 | Created custom `lib/toast.js` toast implementation | Unnecessary — original package works fine in browser |
| 9 | Created `next.config.js` with webpack SSR alias to stub toast | Disabled toast entirely on server, breaking UX |
| 10 | Created `lib/ssr-toast-stub.js` | Redundant |
| 11 | Switched Dockerfile from `next start` (SSR) to nginx static export | Required new config files, still crashed during build |
| 12 | Switched Dockerfile back from nginx to `next start` | Circular — wasted 2 build cycles |
| 13 | Removed `react-hot-toast` from `package.json` entirely | All import references now failed |
| 14 | Ran `sed` to replace 6+ imports from `react-hot-toast` to `lib/toast` | Lost track of state across files |
| 15 | Created `nginx.conf` and `styles/toast.css` | Unnecessary artifacts |
| 16 | Cleared `.next` cache and rebuilt multiple times | Forced full rebuilds each time (~80 seconds per build) |
| 17 | Proposed rewriting frontend from scratch in plain HTML/JS | Massive over-escalation |
| 18 | Proposed rewriting frontend in Vite + React | Over-escalation |
| 19 | Proposed rewriting frontend in Next.js from scratch | Over-escalation |

**Summary: ~20 file modifications across 8 files, 15 Docker build attempts, zero successful frontend loads.**

## 5. Failure Patterns

### Pattern 1: Rushed to action instead of diagnosis
The model never read the working Certa AI frontend (running on port 3000, same codebase fork) until explicitly instructed by the user. The fix was visible in the working code the entire time.

### Pattern 2: Too many simultaneous changes
The model modified hooks, pages, Dockerfile, package.json, and config files all at once. When the build failed, the model couldn't determine which change caused the failure, leading to more random changes.

### Pattern 3: Unreliable `replace_in_file` usage
The SEARCH pattern `}` was used to append code to a 716-line file. This matched in multiple places, corrupting the file repeatedly. The model should have used `write_to_file` for definitive full-file replacements.

### Pattern 4: Escalation spiral
Instead of fixing 3 lines of code, the model proposed rebuilding the entire frontend from scratch (Next.js rewrite, Vite migration, plain HTML/JS conversion). Each proposal was successively more radical and time-consuming.

### Pattern 5: Ignored reference implementation
The Certa AI frontend at `/Users/mohammadabdulhuq/Downloads/Aye_AI/Agent_AI/frontend` had identical code and was running perfectly. The model only investigated it after the user explicitly asked.

### Pattern 6: Repeated the same failing approach
The model added and removed `getServerSideProps` multiple times — each time placing it in a slightly different (wrong) location via bad `replace_in_file` matches.

## 6. Expected Behavior

A competent model should have:
1. Recognized that `react-hot-toast` fails during Next.js static prerendering (well-known issue)
2. Applied the standard fix: import `react-hot-toast` normally, add `getServerSideProps` to skip prerendering
3. Tested and succeeded within 2-3 iterations

## 7. Environment

- **Model:** DeepSeek (via Cline VS Code extension with user-provided API key)
- **Framework:** Next.js 13.5.6, React 18.2.0, `react-hot-toast` 2.4.1
- **Runtime:** Docker Compose on macOS
- **Task scope:** One-port remap (8000→8002) + one file fix (add 3 lines to index.js)

## 8. Estimated Cost

- **Actual time spent:** ~60 minutes
- **Expected time:** 2-3 minutes
- **Build cycles wasted:** ~15 Docker builds at ~80 seconds each = ~20 minutes of CPU time
- **Files unnecessarily modified/created:** 8+ files with changes that were later reverted

## 9. Root Cause Summary

The model lacked systematic debugging discipline:
- Did not isolate the problem (react-hot-toast vs. prerendering)
- Did not test changes incrementally
- Did not check for known working references
- Persisted with failing approaches instead of stepping back to diagnose