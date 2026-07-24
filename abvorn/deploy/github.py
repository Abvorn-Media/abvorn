import os, json, logging, base64, re, html
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger("abvorn.deploy")

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{tags}">
{seo_tags}
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<article>
<h1>{title}</h1>
{content}
</article>
<script type="application/ld+json">{schema}</script>
</body>
</html>"""

class GitHubDeployer:
    """Deploys content to GitHub Pages via the GitHub API."""

    def __init__(self, token: str, repo: str, branch: str = "main", site_dir: str = ""):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.site_dir = Path(site_dir) if site_dir else Path("docs")

    def prepare_files(self, content: dict, output_dir: Path) -> list[str]:
        """Generate HTML files for a content item."""
        slug = content.get("niche_slug", content.get("post_title", "post").lower().replace(" ", "-"))
        safe_slug = re.sub(r'[^a-z0-9-]', '', slug.lower())[:80]

        article_html = content.get("article_html", "")
        intro = content.get("intro", "")
        meta_desc = content.get("meta_description", "")[:160]
        title = html.escape(content.get("post_title", "Post"), quote=True)
        tags_str = ", ".join(content.get("tags", []))
        schema_json = json.dumps(content.get("schema", {}))

        seo_tags = f'<link rel="canonical" href="https://{self.repo.split("/")[0]}.github.io/{self.repo.split("/")[1]}/{safe_slug}/">'

        full_html = TEMPLATE.format(
            title=title, meta_desc=meta_desc, tags=tags_str,
            seo_tags=seo_tags, content=intro + "\n" + article_html,
            schema=schema_json,
        )

        post_dir = output_dir / safe_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        index_file = post_dir / "index.html"
        index_file.write_text(full_html, encoding="utf-8")
        logger.info(f"Prepared: {index_file}")
        return [str(index_file)]

    def deploy(self, niche_slug: str) -> dict:
        """Push generated files to GitHub using PyGithub."""
        from github import Github
        from github import InputGitTreeElement

        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo)
            site_path = self.site_dir / niche_slug / "index.html"

            if not site_path.exists():
                return {"status": "error", "message": f"File not found: {site_path}"}

            with open(site_path, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                ref = repo.get_git_ref(f"heads/{self.branch}")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)
            except Exception:
                ref = repo.get_git_ref("heads/main")
                base_sha = ref.object.sha
                base_tree = repo.get_git_tree(base_sha)

            blob = repo.create_git_blob(content, "utf-8")
            relative_path = str(self.site_dir.name / niche_slug / "index.html")
            element = InputGitTreeElement(relative_path, "100644", "blob", sha=blob.sha)
            new_tree = repo.create_git_tree([element], base_tree)

            parent = repo.get_git_commit(base_sha)
            commit = repo.create_git_commit(f"feat: deploy {niche_slug}", new_tree, [parent])
            ref.edit(commit.sha)

            deploy_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/{niche_slug}/"
            logger.info(f"Deployed: {deploy_url}")
            return {"status": "success", "url": deploy_url, "commit": commit.sha}

        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return {"status": "error", "message": str(e)}