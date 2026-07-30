with open(r"C:\Users\Jean Mare\Documents\Default Project\run_cycle.py", encoding="utf-8") as f:
    content = f.read()

# Insert batch_process_niches before def main(forced_niche
insert_text = '''

def batch_process_niches(niches: List[Dict], workflow_name: str = None) -> Dict[str, Any]:
    """Process multiple niches in parallel using the DAG scheduler."""
    global _dag_scheduler, _workflow_engine

    if not niches:
        return {"status": "idle", "message": "No niches to process"}

    logger.info(f"Batch processing {len(niches)} niches via DAG")

    dag = DAG(
        id=f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name=f"Batch processing {len(niches)} niches",
    )

    for i, niche in enumerate(niches):
        task = Task(
            id=f"niche_{i}_{niche.get('slug', 'unknown')}",
            name=f"Process {niche.get('slug', 'unknown')}",
            func=process_single_niche,
            kwargs={"niche": niche, "workflow_name": workflow_name},
            max_retries=2,
            timeout=600,
        )
        dag.tasks[task.id] = task

    _dag_scheduler.register_dag(dag)
    result = _dag_scheduler.execute_dag(dag_id=dag.id)
    return result


def process_single_niche(niche: Dict, workflow_name: str = None) -> Dict:
    """Process a single niche — used as a DAG task worker."""
    global ai_sql, _knowledge_core, _workflow_engine, _dag_scheduler

    niche_slug = niche.get("slug", "unknown")
    niche_name = niche.get("name", niche_slug.replace("_", " ").title())

    # 1. Research
    products = research_products(niche_slug)
    if not products:
        return {"status": "error", "message": f"No products found for {niche_slug}"}

    # 2. Outline
    outline = generate_outline(niche_slug, products, _knowledge_core, _workflow_engine)
    if not outline:
        outline = {
            "post_title": f"Best {niche_name}",
            "meta_description": f"Find the best {niche_name}.",
            "selected_angle": "problem_solution",
            "primary_keyword": f"best {niche_slug}",
        }

    # 3. Draft
    draft = write_draft(niche_slug, products, outline, _knowledge_core, _workflow_engine)
    if not draft:
        return {"status": "error", "message": f"Draft failed for {niche_slug}"}

    # 4. Publish
    try:
        state = load_state()
        articles = {niche_slug: [draft]}
        write_files(niche_slug, articles, state,
                    pexels_key=get_secrets().get("PEXELS_KEY", ""),
                    amazon_tag=get_secrets().get("AMAZON_TAG", "viraltestco-20"))
        niche["posts"] = niche.get("posts", 0) + 1
        save_state(state)
    except Exception as e:
        return {"status": "error", "message": f"Publish failed for {niche_slug}: {e}"}

    return {
        "status": "success",
        "niche": niche_slug,
        "title": draft.get("post_title", ""),
        "size": len(draft.get("article_html", "")),
    }


'''

idx = content.find("def main(forced_niche")
if idx == -1:
    print("ERROR: def main(forced_niche not found!")
else:
    new_content = content[:idx] + insert_text + content[idx:]
    with open(r"C:\Users\Jean Mare\Documents\Default Project\run_cycle.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Inserted batch_process_niches before main() at position {idx}")
    print(f"New total lines: {new_content.count(chr(10))}")
