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
    ('dashboard', 'DASHBOARD', '01_dashboard'),
    ('datasets', 'DATASETS', '02_datasets'),
    ('strategies', 'STRATEGIES', '03_strategies'),
    ('backtests', 'BACKTESTS', '04_backtests'),
    ('deployments', 'DEPLOYMENTS', '05_deployments'),
    ('live', 'LIVE TRADING', '06_live_trading_sidebar'),
]

for tab_id, tab_name, filename in tabs:
    click_code = f"""
    (() => {{
        const buttons = Array.from(document.querySelectorAll('button'));
        const btn = buttons.find(b => b.textContent.trim() === '{tab_name}');
        if (btn) {{
            const ev = new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }});
            btn.dispatchEvent(ev);
            return 'clicked ' + btn.textContent;
        }}
        return 'not found: {tab_name}';
    }})()
    """
    result = req('evaluate', {'code': click_code})
    print(f"{tab_name}: {result}")
    time.sleep(3)
    resp = req('screenshot', {'format': 'png', 'path': f'{out_dir}/{filename}.png'})
    print(f"  -> {resp['data']['sizeBytes']} bytes")
