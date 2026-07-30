with open(r"C:\Users\Jean Mare\Documents\Default Project\run_cycle.py", encoding="utf-8") as f:
    content = f.read()

# Add batch mode logic: when batch_mode, process all queued niches
old = """    total = sum(n["posts"] for n in state["niches"])
    print(f"\\n{'='*50}")
    print(f"[OK] Cycle complete: {niche_slug}")
    print(f"   Total posts on site: {total}")
    print(f"   Next up: next niche in round-robin")
    print(f"{'='*50}")"""

new = """    total = sum(n["posts"] for n in state["niches"])
    print(f"\\n{'='*50}")
    print(f"[OK] Cycle complete: {niche_slug}")
    print(f"   Total posts on site: {total}")
    print(f"   Next up: next niche in round-robin")
    print(f"{'='*50}")

    # Batch mode: process remaining niches in parallel via DAG
    if batch_mode:
        remaining = [n for n in state["niches"] if n["slug"] != niche_slug and n["posts"] < 3]
        if remaining:
            print(f"\\n--- BATCH MODE: {len(remaining)} niches remaining ---")
            batch_result = batch_process_niches(remaining)
            return {"status": "batch_complete", "results": batch_result}"""

if old in content:
    new_content = content.replace(old, new, 1)
    with open(r"C:\Users\Jean Mare\Documents\Default Project\run_cycle.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Batch mode logic added to main()")
else:
    print("ERROR: Could not find the target text to replace")
    # Show what's near the summary section
    idx = content.find("Total posts on site")
    if idx > 0:
        print(f"Found at position {idx}")
        print(repr(content[idx-50:idx+200]))
    else:
        print("Could not find 'Total posts on site' either")
