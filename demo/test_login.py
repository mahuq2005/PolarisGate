"""Quick login validation — test both main dashboard and chat page."""
from playwright.sync_api import sync_playwright
import time

EMAIL = 'admin@polarisgate.ai'
PASSWORD = 'PolarisGateDemo2024!'

pw = sync_playwright().start()
browser = pw.chromium.launch(headless=True)
page = browser.new_page(viewport={'width': 1280, 'height': 800})

# Test 1: Main dashboard login
print('=== Test 1: Main Dashboard Login ===')
page.goto('http://localhost:3001')
time.sleep(1)
page.fill('#login-email', EMAIL)
page.fill('#login-password', PASSWORD)
page.click('#login-btn')
try:
    page.wait_for_selector('#dashboard-screen:not(.hidden)', timeout=8000)
    print('PASS: Dashboard login OK')
except:
    print('FAIL: Dashboard login')

# Test 2: Chat page login
print('=== Test 2: Chat Page Login ===')
page.goto('http://localhost:3001/chat.html')
time.sleep(2)
page.fill('#login-email', EMAIL)
page.fill('#login-password', PASSWORD)
page.click('button:has-text("Login")')
time.sleep(2)
display = page.evaluate("document.getElementById('chat-app').style.display")
if display == 'block':
    print('PASS: Chat login OK (display=block)')
else:
    print(f'WARN: Chat app display={display}, trying JS login...')
    page.evaluate("handleChatLogin()")
    time.sleep(3)
    display = page.evaluate("document.getElementById('chat-app').style.display")
    print(f'After JS login: display={display}')

# Test 3: Send a message
print('=== Test 3: Chat Send Message ===')
page.evaluate("sendSuggestion('Explain quantum computing in simple terms')")
time.sleep(4)
msg_count = page.evaluate("document.querySelectorAll('.msg-group').length")
print(f'Messages rendered: {msg_count}')
if msg_count >= 2:
    print('PASS: Chat messages flowing')
else:
    print('WARN: Few messages')

browser.close()
pw.stop()
print('\nDone.')