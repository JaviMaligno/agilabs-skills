# E2E Testing Patterns with Chrome DevTools MCP

**Load this reference when:** verifying deployments, testing user flows, or debugging frontend issues on deployed services.

## Chrome Launch Command

Launch Chrome with a remote debugging port before using any Chrome DevTools MCP tools. The exact command is OS-specific; the debugging flags are the same everywhere.

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-debug-profile" \
  "about:blank"

# Linux
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-debug-profile" \
  "about:blank"

# Windows
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%USERPROFILE%\chrome-debug-profile" ^
  "about:blank"
```

**Note:** Always launch Chrome with debugging BEFORE attempting to use Chrome DevTools MCP tools. Use a dedicated `--user-data-dir` (not your normal profile) to avoid conflicts.

## Basic Verification Flow

```python
# 1. Navigate to target
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com")

# 2. Wait for page load
mcp__chrome-devtools__wait_for(selector="body", timeout=10000)

# 3. Take snapshot for DOM analysis
mcp__chrome-devtools__take_snapshot()

# 4. Check for JavaScript errors
mcp__chrome-devtools__list_console_messages()
# Look for: errors, warnings, failed network requests

# 5. Screenshot for visual verification
mcp__chrome-devtools__take_screenshot()

# 6. Check network requests
mcp__chrome-devtools__list_network_requests()
# Verify: all API calls returning 200/201, no 4xx/5xx errors
```

## Login Flow Testing

```python
# Navigate to login
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com/login")

# Wait for form to load
mcp__chrome-devtools__wait_for(selector="input[name='email']", timeout=10000)

# Fill credentials
mcp__chrome-devtools__fill(selector="input[name='email']", value="test@example.com")
mcp__chrome-devtools__fill(selector="input[name='password']", value="testpassword")

# Submit form
mcp__chrome-devtools__click(selector="button[type='submit']")

# Wait for redirect to dashboard/home
mcp__chrome-devtools__wait_for(selector=".dashboard", timeout=15000)

# Verify success with screenshot
mcp__chrome-devtools__take_screenshot()

# Check for any auth errors in console
mcp__chrome-devtools__list_console_messages()
```

## API Integration Testing

```python
# Trigger an action that makes API call (e.g., load data)
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com/items")

# Wait for data to load
mcp__chrome-devtools__wait_for(selector=".item-card", timeout=15000)

# Check all network requests
mcp__chrome-devtools__list_network_requests()

# Get specific request details if needed
mcp__chrome-devtools__get_network_request(request_id="...")

# Verify:
# - API calls to backend return 200
# - No CORS errors
# - Response times are acceptable
# - No failed requests (4xx, 5xx)
```

## Form Submission Testing

```python
# Navigate to form page
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com/profile")

# Fill form using fill_form for structured data
mcp__chrome-devtools__fill_form(
    fields=[
        {"selector": "input[name='name']", "value": "Test User"},
        {"selector": "input[name='email']", "value": "test@example.com"},
        {"selector": "textarea[name='bio']", "value": "Test bio content"}
    ]
)

# Submit
mcp__chrome-devtools__click(selector="button[type='submit']")

# Wait for success indicator
mcp__chrome-devtools__wait_for(selector=".success-message", timeout=10000)

# Screenshot confirmation
mcp__chrome-devtools__take_screenshot()
```

## File Upload Testing

```python
# Navigate to upload page
mcp__chrome-devtools__navigate_page(url="https://your-app.onrender.com/upload")

# Upload file
mcp__chrome-devtools__upload_file(
    selector="input[type='file']",
    file_path="/path/to/test-file.pdf"
)

# Submit upload
mcp__chrome-devtools__click(selector="button.upload-submit")

# Wait for upload completion
mcp__chrome-devtools__wait_for(selector=".upload-success", timeout=30000)

# Verify
mcp__chrome-devtools__take_screenshot()
```

## Debugging Deployment Issues

### White Screen
```python
# Check console for JavaScript errors
mcp__chrome-devtools__list_console_messages()
# Look for: ReferenceError, TypeError, SyntaxError

# Check network for failed asset loads
mcp__chrome-devtools__list_network_requests()
# Look for: 404 on JS/CSS files, failed chunk loads
```

### API Failures
```python
# Monitor network requests
mcp__chrome-devtools__list_network_requests()
# Look for: 4xx/5xx responses, CORS errors

# Get specific failed request details
mcp__chrome-devtools__get_network_request(request_id="...")
# Check: response body, headers, timing
```

### Slow Loading
```python
# Take snapshot to see what's rendered
mcp__chrome-devtools__take_snapshot()

# Check network waterfall
mcp__chrome-devtools__list_network_requests()
# Identify: slow API calls, large assets, blocking resources
```

### Authentication Issues
```python
# Check console for auth errors
mcp__chrome-devtools__list_console_messages()

# Check network for failed auth requests
mcp__chrome-devtools__list_network_requests()
# Look for: 401/403 responses, missing tokens

# Verify cookies/storage via evaluate_script if needed
mcp__chrome-devtools__evaluate_script(
    script="JSON.stringify(document.cookie)"
)
```

## Handling Dialogs and Popups

```python
# Handle confirmation dialog
mcp__chrome-devtools__handle_dialog(action="accept")

# Handle prompt dialog with input
mcp__chrome-devtools__handle_dialog(action="accept", text="User input")

# Dismiss dialog
mcp__chrome-devtools__handle_dialog(action="dismiss")
```

## Quick Verification Checklist

After every deployment, run this minimum verification:

1. [ ] `navigate_page` to deployed URL
2. [ ] `wait_for` main content selector
3. [ ] `take_screenshot` for visual check
4. [ ] `list_console_messages` for JS errors
5. [ ] `list_network_requests` for API failures
6. [ ] Test one key user flow (login, data load, etc.)

**Never skip these steps. Screenshots are evidence of success.**
