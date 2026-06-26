import requests, json, time, os

session = 'quantlab-docs'
base = 'http://127.0.0.1:10086/command'
out_dir = 'C:/Users/rajy7/quantp/screenshots'

def req(action, args):
    r = requests.post(base, json={'action': action, 'args': args, 'session': session})
    return r.json()

# Navigate to main page and wait for React to mount
req('navigate', {'url': 'http://localhost:3000', 'newTab': False})
time.sleep(5)

tabs = [
    ('Dashboard', '01_dashboard'),
    ('Datasets', '02_datasets'),
    ('Strategies', '03_strategies'),
    ('Backtests', '04_backtests'),
    ('Deployments', '05_deployments'),
    ('Live Trading', '06_live_trading_sidebar'),
    ('Strategy Registry', '07_strategy_registry'),
    ('Research Lab', '08_research_lab'),
    ('Multi-Asset', '09_multi_asset'),
    ('Portfolio Risk', '10_portfolio_risk'),
    ('Optimizer', '11_optimizer'),
    ('Cleanup', '12_cleanup'),
]

for tab_name, filename in tabs:
    click_code = f"""
    (() => {{
        const buttons = Array.from(document.querySelectorAll('button'));
        const btn = buttons.find(b => b.textContent.trim() === '{tab_name}');
        if (btn) {{
            const ev = new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }});
            btn.dispatchEvent(ev);
            return 'clicked ' + btn.textContent.trim();
        }}
        return 'not found: {tab_name}';
    }})()
    """
    result = req('evaluate', {'code': click_code})
    print(f"{tab_name}: {result}")
    time.sleep(3)
    resp = req('screenshot', {'format': 'png', 'path': f'{out_dir}/{filename}.png'})
    print(f"  -> {resp['data']['sizeBytes']} bytes")

# Also navigate to /live page
req('navigate', {'url': 'http://localhost:3000/live', 'newTab': True})
time.sleep(4)
resp = req('screenshot', {'format': 'png', 'path': f'{out_dir}/13_live_page.png'})
print(f"LIVE PAGE: {resp['data']['sizeBytes']} bytes")
