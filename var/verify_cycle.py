import json, os, glob
from datetime import datetime

DATA = '/opt/abvorn-core/data'

# Cycle state
print("=== CYCLE STATE ===")
try:
    d = json.load(open('/opt/abvorn-core/cycle_state.json'))
    print("last_processed:", d.get('last_processed'))
    print("niches (posts):")
    for n in d.get('niches', []):
        print("  %s: %d" % (n.get('slug'), n.get('posts', 0)))
except Exception as e:
    print("error:", e)

# Reflections
print("\n=== REFLECTIONS ===")
refs = sorted(glob.glob(os.path.join(DATA, 'reflections', '*.json')))
print("total reflections:", len(refs))
for f in refs[-3:]:
    stamp = os.path.getmtime(f)
    print("  %s (mtime %s)" % (os.path.basename(f), datetime.fromtimestamp(stamp).isoformat()))

# Outcomes
print("\n=== OUTCOMES (last 3) ===")
op = os.path.join(DATA, 'outcomes.jsonl')
if os.path.exists(op):
    lines = open(op).readlines()
    print("total outcome lines:", len(lines))
    for l in lines[-3:]:
        print(" ", l.strip()[:150])

# Relentless state
print("\n=== RELENTLESS STATE ===")
try:
    r = json.load(open(os.path.join(DATA, 'relentless_state.json')))
    print("status:", r.get('status'), "| last_action:", r.get('last_action'), "| ts:", r.get('timestamp'))
except Exception as e:
    print("error:", e)

# GSC summary
print("\n=== GSC SUMMARY ===")
g = os.path.join(DATA, 'gsc_latest_summary.json')
print("exists:", os.path.exists(g))
