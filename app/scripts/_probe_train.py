import json
from playwright.sync_api import sync_playwright
sh = json.load(open('data/shutuba_20260627.json'))
rid = sh[0]['race_id']
url = f"https://race.netkeiba.com/race/oikiri.html?race_id={rid}&type=2"
JS = r"""
() => {
  const out = [];
  document.querySelectorAll("a[href*='/horse/']").forEach(a => {
    const name = (a.textContent||"").trim();
    if (!name) return;
    let row = a;
    for (let i=0; i<7 && row; i++){
      row = row.parentElement;
      if (row && /\d{1,2}\.\d/.test(row.textContent)) break;
    }
    const txt = row ? row.textContent.replace(/\s+/g," ").trim() : "";
    const times = (txt.match(/\d{1,2}\.\d/g) || []).slice(0,8);
    if (times.length) out.push({name, times, raw: txt.slice(0,140)});
  });
  return out;
}
"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    data = page.evaluate(JS)
    b.close()
json.dump(data, open('/tmp/train_probe.json','w'), ensure_ascii=False, indent=1)
print(len(data))
