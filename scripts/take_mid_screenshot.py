from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:5175')
    page.wait_for_timeout(2000)
    page.click('.asset-card')
    page.wait_for_timeout(2000)
    page.select_option('select', 'DE40')
    page.wait_for_timeout(1000)
    # Click the MID button
    mid_buttons = page.query_selector_all('button')
    for btn in mid_buttons:
        if btn.inner_text().strip() == 'MID':
            btn.click()
            break
    page.wait_for_timeout(1000)
    page.screenshot(path=r'c:\Users\ryzen\.gemini\antigravity-ide\brain\428eb6d5-a258-4f21-9a01-d851e0afac54\de40_mid_gex_evidence.png')
    print('DE40 MID walls screenshot saved!')
    browser.close()
