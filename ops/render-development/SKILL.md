---
name: render-development
description: Use when deploying, managing, or testing services on Render.com - includes PostgreSQL management and Chrome E2E verification
---

# Render Development

## Overview

Comprehensive workflow for deploying and managing applications on Render.com with full PostgreSQL support and automated E2E testing via Chrome DevTools MCP.

**Core principle:** Deploy → Configure → Migrate → Verify (with Chrome MCP screenshots).

**REQUIRED BACKGROUND:** Familiarity with Render MCP tools (mcp__render__*) and Chrome DevTools MCP (mcp__chrome-devtools__*).

**Adapting to other platforms:** this skill is written for Render.com, but the reusable
parts are platform-agnostic — the Deploy → Configure → Migrate → Verify discipline, the
"check logs immediately / never skip E2E / screenshots as evidence" rules, the
internal-vs-external Postgres connection-string distinction, and the Chrome-MCP E2E
patterns all transfer to Fly.io, Railway, Vercel, or a raw VPS. Swap the `mcp__render__*`
tool calls for your platform's CLI/API and keep the workflow.

## When to Use

- Deploying a web service or background worker to Render
- Creating or managing PostgreSQL instances on Render
- Configuring environment variables for Render services
- Running E2E tests against deployed services
- Debugging deployment issues with logs
- Verifying UI/UX after deployment changes

## Quick Reference - Render MCP Tools

| Tool | Purpose |
|------|---------|
| `mcp__render__list_services` | List all services |
| `mcp__render__get_service` | Get service details |
| `mcp__render__create_web_service` | Create new service |
| `mcp__render__update_web_service` | Update service config |
| `mcp__render__update_environment_variables` | Set env vars |
| `mcp__render__list_deploys` | View deployment history |
| `mcp__render__list_logs` | View service logs |
| `mcp__render__create_postgres` | Create PostgreSQL instance |
| `mcp__render__get_postgres` | Get database details |
| `mcp__render__query_render_postgres` | Execute SQL queries |

## Quick Reference - Chrome DevTools MCP Tools

| Tool | Purpose |
|------|---------|
| `mcp__chrome-devtools__navigate_page` | Navigate to URL |
| `mcp__chrome-devtools__take_screenshot` | Capture page screenshot |
| `mcp__chrome-devtools__take_snapshot` | Capture DOM snapshot |
| `mcp__chrome-devtools__click` | Click elements |
| `mcp__chrome-devtools__fill` | Fill form inputs |
| `mcp__chrome-devtools__fill_form` | Fill entire forms |
| `mcp__chrome-devtools__list_console_messages` | Check for JS errors |
| `mcp__chrome-devtools__list_network_requests` | Monitor API calls |

## Deployment Workflow

### 1. Pre-Deployment Checklist

- [ ] Code committed and pushed to repository
- [ ] Environment variables documented
- [ ] Database migrations ready (if the service uses a migration tool)
- [ ] Health endpoint implemented (e.g. `/health`)
- [ ] Local tests passing

### 2. Database Setup (if needed)

```
1. mcp__render__list_postgres_instances - Check existing
2. mcp__render__create_postgres - Create new instance
3. mcp__render__get_postgres - Get connection string
4. Update DATABASE_URL in service environment
```

### 3. Service Deployment

```
1. mcp__render__get_service - Check current service status
2. mcp__render__create_web_service OR update_web_service
3. mcp__render__update_environment_variables - Set all env vars
4. mcp__render__list_deploys - Monitor deployment progress
5. mcp__render__list_logs - Check for errors IMMEDIATELY
```

### 4. Post-Deployment Verification (MANDATORY)

```
1. Health check: curl https://your-api.onrender.com/health
2. Chrome E2E: Navigate, screenshot, verify UI
3. API tests: Test key endpoints with curl
4. Console check: Verify no JS errors via Chrome MCP
5. Network check: Verify API calls succeed via Chrome MCP
```

## Exact Deployment Tool Order

Follow this exact sequence for deployments:

```
PRE-DEPLOY:
1. Run your project's test suite / build - Verify local build passes

DEPLOY:
2. mcp__render__list_services         - Find service ID
3. mcp__render__get_service           - Check current status
4. mcp__render__update_environment_variables - If new vars needed
5. mcp__render__list_deploys          - Monitor deployment progress
6. mcp__render__list_logs             - Check for errors IMMEDIATELY

VERIFY (Chrome):
7. Launch Chrome with debugging port
8. mcp__chrome-devtools__navigate_page   - Homepage
9. mcp__chrome-devtools__take_screenshot - Visual check #1
10. mcp__chrome-devtools__list_console_messages - JS errors check
11. mcp__chrome-devtools__list_network_requests - API calls check
12. mcp__chrome-devtools__navigate_page  - Specific changed page
13. mcp__chrome-devtools__take_screenshot - Visual check #2
14. mcp__chrome-devtools__list_console_messages - Page-specific JS errors
15. mcp__chrome-devtools__take_snapshot  - Full DOM verification (optional)
16. mcp__chrome-devtools__take_screenshot - Final confirmation
```

## E2E Testing Pattern

**After ANY deployment, verify with Chrome:**

```bash
# 1. Launch Chrome with debugging (macOS example - adjust path/profile-dir per OS)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-debug-profile" \
  "about:blank"
```

```python
# 2. Navigate to deployed service
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com")

# 3. Take screenshot for verification
mcp__chrome-devtools__take_screenshot()

# 4. Check console for errors
mcp__chrome-devtools__list_console_messages()

# 5. Monitor network requests
mcp__chrome-devtools__list_network_requests()

# 6. Test key user flows
mcp__chrome-devtools__fill(selector="input[name='email']", value="test@example.com")
mcp__chrome-devtools__click(selector="button[type='submit']")
```

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Deploy stuck | Check `list_logs` for build errors |
| 502 Bad Gateway | Service crashed - check logs, verify start command |
| Database connection failed | Verify DATABASE_URL format, check PostgreSQL status |
| CORS errors | Update allowed-origins / FRONTEND_URL in backend env vars |
| WebSocket fails | Ensure WSS URL matches deployed backend |
| Build fails | Check `list_logs`, verify dependencies in your manifest (pyproject.toml/package.json/etc.) |
| Migrations fail | Run migrations with the external DATABASE_URL format (driver + sslmode=require) |

## Integration with Other Skills

- **REQUIRED SUB-SKILL:** Use `frontend-design:frontend-design` for any UI enhancements
- **REQUIRED SUB-SKILL:** Use `superpowers:verification-before-completion` before claiming deployment success
- **REQUIRED SUB-SKILL:** Use `superpowers:systematic-debugging` for deployment failures

## Common Rationalizations to Avoid

| Excuse | Reality |
|--------|---------|
| "I'll check logs later" | Check logs IMMEDIATELY - errors in first 30s are critical |
| "It worked locally" | Render environment differs - always verify with MCP |
| "Screenshots are overkill" | Visual bugs are invisible without screenshots |
| "Health check passed, we're done" | Health check is minimum - verify actual UI and flows |
| "I'll skip E2E this time" | E2E catches issues health checks miss - never skip |

## Red Flags - STOP

**Pre-Deploy Red Flags:**
- Deploying without testing locally first
- Committing secrets to repository
- Skipping database migrations

**During Deploy Red Flags:**
- Deployment status stuck at "building" for more than 10 minutes
- Any ERROR or FATAL in `list_logs` output
- Not checking logs IMMEDIATELY after deploy

**Post-Deploy Red Flags:**
- Assuming deployment succeeded without checking logs
- Skipping Chrome E2E verification
- Not checking console for JavaScript errors
- Declaring success without screenshots
- Network requests returning 404, 500, or CORS errors
- Changed page returning blank/white screen
- Interactive elements not clickable or throwing errors

**All of these mean: STOP and complete the verification workflow.**

**If any deploy red flag occurs:** Use `superpowers:systematic-debugging` to diagnose before proceeding.

## Testing Reference

**Backend Tests:** run your project's unit test suite (run before deploy)
**Frontend Build:** run your project's build command (verify no errors before deploy)
**E2E Verification:** Always use Chrome DevTools MCP after deploy

For detailed PostgreSQL operations, see: postgres-operations.md
For E2E testing patterns, see: e2e-testing-patterns.md
