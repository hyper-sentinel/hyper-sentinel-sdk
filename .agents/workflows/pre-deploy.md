---
description: Mandatory testing gates before any deployment (PyPI, Cloud Run, Vercel)
---

# Pre-Deploy Testing Workflow

**Rule: Test as the user BEFORE deploying anywhere.**

## Gate 1: Does It Run At All?

Before ANY code changes are deployed, verify the thing starts:

### SDK
```bash
pip install -e .
sentinel --version
sentinel auth
```

### Go Gateway
```bash
go build ./cmd/server
curl http://localhost:8080/health
```

### Web Console
```bash
npm run build    # Must compile with zero errors
npm run dev      # Must load in browser
```

// turbo-all

## Gate 2: User Journey Test

Walk through the EXACT flow a real user takes:

### New User (SDK)
1. `pip install hyper-sentinel`
2. `sentinel auth` → Must prompt, must show keys
3. `sentinel tools` → Must list tools
4. `sentinel call get_crypto_price --param coin_id=bitcoin` → Must return data

### New User (Web)
1. Land on console.hyper-sentinel.com
2. Click sign in
3. Enter AI key → Must get to dashboard
4. Settings → API Keys → Generate Key → Must show key
5. Settings → Subscription → Must show 40/20/10

### Returning User (SDK)
1. `sentinel auth` → Must show "Welcome Back"
2. `sentinel status` → Must show account info

// turbo-all

## Gate 3: Error Paths

Test what happens when things go WRONG:

```bash
sentinel auth --key "garbage"         # Must show clear error, not stack trace
sentinel auth --key ""                # Must show clear error
sentinel call nonexistent_tool        # Must show "tool not found"
sentinel status                       # Without auth — must say "not authenticated"
```

// turbo-all

## Gate 4: Deploy

Only after Gates 1-3 pass, deploy to the target:

- **SDK**: Follow /ship-release workflow
- **Go**: `gcloud run deploy ...`  
- **Web**: `npx vercel --prod`

## Gate 5: Smoke Test Production

After deploy, hit the PRODUCTION URLs:

```bash
# Gateway
curl https://api.hyper-sentinel.com/health

# SDK from PyPI
pip install hyper-sentinel==X.Y.Z --no-cache-dir
sentinel auth

# Web
# Open console.hyper-sentinel.com in browser, verify dashboard loads
```

---

*This workflow exists because code was deployed without testing basic user flows.*
