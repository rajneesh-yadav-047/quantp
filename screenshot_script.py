import requests, json, time

session = 'quantlab-docs'
base = 'http://127.0.0.1:10086/command'
out_dir = 'C:/Users/rajy7/quantp/screenshots'

def req(action, args):
    r = requests.post(base, json={'action': action, 'args': args, 'session': session})
    return r.json()

# Navigate to main page and wait
req('navigate', {'url': 'http://localhost:3000', 'newTab': False})
time.sleep(3)

tabs = [
    ('DASHBOARD', '01_dashboard'),
    ('DATASETS', '02_datasets'),
    ('STRATEGIES', '03_strategies'),
    ('BACKTESTS', '04_backtests'),
    ('DEPLOYMENTS', '05_deployments'),
    ('LIVE TRADING', '06_live_trading_sidebar'),
    ('STRATEGY REGISTRY', '07_strategy_registry'),
    ('RESEARCH LAB', '08_research_lab'),
    ('MULTI-ASSET', '09_multi_asset'),
    ('PORTFOLIO RISK', '10_portfolio_risk'),
    ('OPTIMIZER', '11_optimizer'),
    ('CLEANUP', '12_cleanup'),
]

for tab_name, filename in tabs:
    click_code = f"(() => {{ const buttons = Array.from(document.querySelectorAll('button')); const btn = buttons.find(b => b.textContent.trim() === '{tab_name}'); if (btn) {{ btn.click(); return 'clicked'; }} return 'not found'; }})()"
    result = req('evaluate', {'code': click_code})
    print(f"{tab_name}: {result}")
    time.sleep(3)
    resp = req('screenshot', {'format': 'png', 'path': f'{out_dir}/{filename}.png'})
    print(f"  -> {resp['data']['sizeBytes']} bytes")

# Also navigate to /live page
req('navigate', {'url': 'http://localhost:3000/live', 'newTab': True})
time.sleep(3)
resp = req('screenshot', {'format': 'png', 'path': f'{out_dir}/13_live_page.png'})
print(f"LIVE PAGE: {resp['data']['sizeBytes']} bytes")
