import json, logging, re, html, time
from pathlib import Path

logger = logging.getLogger("abvorn.deploy")

PLACEHOLDER_MARKERS = (
    "Categories coming soon",
    "Reviews coming soon",
    "Reviews for this category are being researched",
)

DNA_CSS = {
    "tech": (
        "--font-family: 'Inter', -apple-system, sans-serif;\n"
        "--border-radius: 2px;\n"
        "--card-style: flat;\n"
        "--button-style: outline;\n"
        "--button-radius: 2px;\n"
        "--image-radius: 2px;\n"
        "--spacing-unit: 8px;\n"
        "--heading-weight: 700;\n"
    ),
    "warm": (
        "--font-family: 'Nunito', -apple-system, sans-serif;\n"
        "--border-radius: 12px;\n"
        "--card-style: shadow;\n"
        "--button-style: filled;\n"
        "--button-radius: 24px;\n"
        "--image-radius: 16px;\n"
        "--spacing-unit: 12px;\n"
        "--heading-weight: 600;\n"
    ),
    "premium": (
        "--font-family: 'Playfair Display', 'Lora', serif;\n"
        "--border-radius: 0px;\n"
        "--card-style: elevated;\n"
        "--button-style: ghost;\n"
        "--button-radius: 0px;\n"
        "--image-radius: 0px;\n"
        "--spacing-unit: 16px;\n"
        "--heading-weight: 400;\n"
    ),
}

def _is_non_fast_forward(exc: Exception) -> bool:
    """True for GitHub's 'Update is not a fast forward' rejection of a ref edit.

    That is a lost race against another writer, not a bad request, and it is
    worth retrying. 422 also covers genuine validation failures, so match the
    message rather than the status alone.
    """
    return getattr(exc, "status", None) == 422 and "fast forward" in str(exc)


class GitHubDeployer:
    """Deploys content to GitHub Pages via the GitHub API."""

    def __init__(self, token: str, repo: str, branch: str = "main", site_dir: str = ""):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.site_dir = Path(site_dir) if site_dir else Path("docs")
        self._tree_paths = None
        self._tree_fetched = 0.0
        self._tree_ttl = 30.0

    def prepare_files(self, content: dict, output_dir: Path, brand=None, state=None) -> list[str]:
        """Generate HTML files for a content item."""
        slug = content.get("niche_slug", content.get("post_title", "post").lower().replace(" ", "-"))
        safe_slug = re.sub(r'[^a-z0-9-]', '', slug.lower())[:80]

        article_html = content.get("article_html", "")
        intro = content.get("intro", "")
        meta_desc = content.get("meta_description", "")[:160]
        title = html.escape(content.get("post_title", "Post"), quote=True)
        tags_str = ", ".join(content.get("tags", []))
        schema_json = json.dumps(content.get("schema", {}))

        site_name = brand.brand_name if brand else "Abvorn"
        primary_color = getattr(brand, 'primary_color', '#1a73e8') if brand else '#1a73e8'
        secondary_color = getattr(brand, 'secondary_color', '#34a853') if brand else '#34a853'
        dna_profile = getattr(brand, 'dna_profile', None)
        dna_value = dna_profile.value if dna_profile else ""
        dna_css = DNA_CSS.get(dna_value, "") if dna_value else ""
        body_class = f' class="dna-{dna_value}"' if dna_value else ""
        brand_style = f"--primary:{primary_color};--secondary:{secondary_color};\n{dna_css}" if dna_css else f"--primary:{primary_color};--secondary:{secondary_color};"

        seo_tags = f'<link rel="canonical" href="https://{self.repo.split("/")[0]}.github.io/{self.repo.split("/")[1]}/{safe_slug}/">'

        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — {site_name}</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{tags_str}">
<meta property="og:site_name" content="{site_name}">
{seo_tags}
<link rel="stylesheet" href="/assets/style.css">
<style>:root{{{brand_style}}}</style>
</head>
<body{body_class}>
<article>
<h1>{title}</h1>
{intro}
{article_html}
</article>
<script type="application/ld+json">{schema_json}</script>
</body>
</html>"""

        if brand and state:
            try:
                from ..persuasion.context import ContextParser
                from ..persuasion.matcher import ProductMatcher
                from ..persuasion.widget import PersuasionWidget
                ctx = ContextParser().parse(content)
                matcher = ProductMatcher(state)
                recs = matcher.match(ctx)
                widget_html = PersuasionWidget().render(ctx, recs, brand)
                if widget_html:
                    full_html = full_html.replace("</article>", widget_html + "\n</article>")
            except Exception:
                pass

        post_dir = output_dir / safe_slug
        post_dir.mkdir(parents=True, exist_ok=True)
        index_file = post_dir / "index.html"
        index_file.write_text(full_html, encoding="utf-8")
        logger.info(f"Prepared: {index_file}")
        return [str(index_file)]

    def _remote_paths(self) -> set:
        """All file paths under site_dir on the current branch, fetched once as a
        recursive git tree and cached briefly so a deploy batch does not burn one
        API call per file. Real API errors raise (so callers can fail open);
        404s on the branch are treated as a miss."""
        import time
        from github import Github
        now = time.monotonic()
        if self._tree_paths is not None and (now - self._tree_fetched) < self._tree_ttl:
            return self._tree_paths
        g = Github(self.token)
        repo = g.get_repo(self.repo)
        for branch in (self.branch, "main"):
            try:
                ref = repo.get_git_ref(f"heads/{branch}")
                break
            except Exception:
                continue
        else:
            raise RuntimeError("branch not found: " + self.branch)
        tree = repo.get_git_tree(ref.object.sha, recursive=True)
        prefix = (str(self.site_dir) + "/").replace("\\", "/")
        self._tree_paths = {
            el.path[len(prefix):]
            for el in tree.tree
            if el.type == "blob" and el.path.startswith(prefix)
        }
        self._tree_fetched = now
        return self._tree_paths

    def file_exists(self, repo_relative_path: str) -> bool:
        """True if a file exists on the remote branch — the source of truth for
        the ready-to-deploy tree. Local clones drift because the daemon pushes
        via the GitHub API and never updates docs/ locally, so cards must be
        gated on the remote tree, not the local checkout.

        Returns only True (definite hit) or False (definite miss). Any API/
        transport error raises so callers can fail open and keep the card
        rather than dropping real pages during a GitHub outage."""
        rel = repo_relative_path.replace("\\", "/")
        return rel.lstrip("/") in self._remote_paths()

    def _branch_ref_name(self, repo) -> str:
        """The ref to deploy onto, falling back to main if the configured
        branch does not exist."""
        try:
            repo.get_git_ref(f"heads/{self.branch}")
            return self.branch
        except Exception:
            if self.branch == "main":
                raise
            return "main"

    def _commit_file(self, repo, repo_path: str, content: str, message: str, attempts: int = 3) -> str:
        """Commit one blob onto the branch head and advance the ref.

        This is a read-modify-write against a branch that other writers move:
        a local `git push`, or the other deploy path. Anything landing between
        reading the head and editing the ref makes the edit a non-fast-forward
        and the deploy is lost outright. Re-read the head and rebuild the commit
        on top of it instead. The blob is content addressed, so a retry only
        redoes the tree and the commit.
        """
        from github import InputGitTreeElement

        ref_name = self._branch_ref_name(repo)
        for attempt in range(1, attempts + 1):
            # Re-fetch every attempt: after a rejected edit the cached ref still
            # holds the stale sha, so reusing it would just fail the same way.
            ref = repo.get_git_ref(f"heads/{ref_name}")
            base_sha = ref.object.sha
            base_tree = repo.get_git_tree(base_sha)
            blob = repo.create_git_blob(content, "utf-8")
            element = InputGitTreeElement(repo_path, "100644", "blob", sha=blob.sha)
            new_tree = repo.create_git_tree([element], base_tree)
            commit = repo.create_git_commit(message, new_tree, [repo.get_git_commit(base_sha)])
            try:
                ref.edit(commit.sha)
                return commit.sha
            except Exception as exc:
                if not _is_non_fast_forward(exc) or attempt == attempts:
                    raise
                logger.warning(
                    f"branch moved while committing {repo_path}; rebuilding on the new head "
                    f"(attempt {attempt}/{attempts})"
                )
                time.sleep(1.5 * attempt)

    def deploy_html(self, html_content: str, output_path: str) -> dict:
        """Push a raw HTML string to a specific path in the repo."""
        for marker in PLACEHOLDER_MARKERS:
            if marker in html_content:
                logger.warning(
                    f"Skipping deploy of {output_path}: content contains placeholder marker {marker!r} "
                    "(refusing to overwrite real page with placeholder)"
                )
                return {"status": "error", "message": "placeholder content blocked", "path": output_path}
        from github import Github
        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo)
            repo_path = (str(self.site_dir) + "/" + output_path).replace("\\", "/")
            commit_sha = self._commit_file(repo, repo_path, html_content, f"deploy: {output_path}")
            logger.info(f"Deployed: {output_path}")
            return {"status": "success", "commit": commit_sha}
        except Exception as e:
            logger.error(f"deploy_html failed for {output_path}: {e}")
            return {"status": "error", "message": str(e)}

    def deploy(self, niche_slug: str) -> dict:
        """Push generated files to GitHub using PyGithub."""
        from github import Github

        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo)
            site_path = self.site_dir / niche_slug / "index.html"

            if not site_path.exists():
                return {"status": "error", "message": f"File not found: {site_path}"}

            with open(site_path, "r", encoding="utf-8") as f:
                content = f.read()

            relative_path = (str(self.site_dir) + "/" + niche_slug + "/index.html").replace("\\", "/")
            commit_sha = self._commit_file(repo, relative_path, content, f"feat: deploy {niche_slug}")

            deploy_url = f"https://{self.repo.split('/')[0]}.github.io/{self.repo.split('/')[1]}/{niche_slug}/"
            logger.info(f"Deployed: {deploy_url}")
            return {"status": "success", "url": deploy_url, "commit": commit_sha}

        except Exception as e:
            logger.error(f"Deploy failed for {niche_slug}: {e}")
            return {"status": "error", "message": str(e)}