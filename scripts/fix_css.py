"""Fix CSS in homepage and all category pages to use premium design."""
from pathlib import Path

CSS_SHARED = """
:root{--primary:#1a1a1a;--primary-dark:#0a0a0a;--primary-light:#f6f5f2;--accent:#c98a2c;--accent-dark:#996015;--green:#059669;--green-light:#d1fae5;--purple:#7c3aed;--purple-light:#ede9fe;--bg:#fff;--bg-alt:#f6f5f2;--text:#1a1a1a;--text-secondary:#666;--text-muted:#666;--border:#e8e8e8;--shadow-sm:0 1px 2px rgba(0,0,0,.04);--shadow-md:0 4px 12px rgba(0,0,0,.06);--shadow-lg:0 8px 24px rgba(0,0,0,.08);--radius-sm:8px;--radius-md:12px;--radius-lg:16px;--font-display:'Libre Franklin',-apple-system,sans-serif;--font-body:'Inter',-apple-system,BlinkMacSystemFont,sans-serif}
@media(prefers-color-scheme:dark){:root{--bg:#0a0a0a;--bg-alt:#1a1a1a;--text:#e2e8f0;--text-secondary:#94a3b8;--text-muted:#666;--border:#2a2a2a}}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;font-family:var(--font-body);-webkit-font-smoothing:antialiased;scroll-behavior:smooth;touch-action:manipulation}
body{color:var(--text);background:var(--bg);line-height:1.6}
::selection{background:rgba(201,138,44,.15)}
.container{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:var(--primary);text-decoration:none;transition:color .15s}
a:hover{color:var(--primary-dark);text-decoration:underline}
nav{background:rgba(255,255,255,.88);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:10}
@media(prefers-color-scheme:dark){nav{background:rgba(10,10,10,.92)}}
nav .inner{max-width:1080px;margin:0 auto;padding:0 24px;display:flex;align-items:center;height:56px;justify-content:space-between}
nav .logo{display:flex;align-items:center;gap:8px;font-weight:700;font-size:1.1rem;color:var(--text);text-decoration:none}
nav .logo img{height:28px;width:auto}
nav .logo:hover{text-decoration:none}
.nav-links{display:flex;align-items:center;gap:24px}
.dropdown{position:relative}
.dropdown-btn{background:none;border:none;cursor:pointer;font-size:.9rem;color:var(--text-secondary);padding:4px 0;border-bottom:2px solid transparent;font-family:inherit;display:flex;align-items:center;gap:4px;transition:color .15s}
.dropdown-btn:hover{color:var(--text);border-bottom-color:var(--primary)}
.dropdown-btn::after{content:'';display:inline-block;width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:4px solid var(--text-muted);margin-left:4px;transition:transform .2s}
.dropdown-menu{display:none;position:absolute;top:100%;left:0;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);box-shadow:var(--shadow-lg);min-width:200px;padding:8px;z-index:20;max-height:400px;overflow-y:auto}
.dropdown:hover .dropdown-menu{display:block}
.dropdown-menu a{display:block;padding:8px 12px;font-size:.9rem;color:var(--text-secondary);border-radius:4px;text-decoration:none;transition:all .15s}
.dropdown-menu a:hover{background:var(--bg-alt);color:var(--primary);text-decoration:none}
.nav-link{font-size:.9rem;color:var(--text-secondary);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent;white-space:nowrap;transition:all .15s}
.nav-link:hover{color:var(--text);border-bottom-color:var(--primary);text-decoration:none}
h1,h2,h3{font-family:var(--font-display)}
h1{font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;letter-spacing:-0.02em;line-height:1.15;color:var(--text)}
h2{font-size:clamp(1.3rem,2.5vw,1.6rem);font-weight:700;margin-bottom:20px;letter-spacing:-0.01em;color:var(--text)}
h3{font-size:clamp(1.1rem,2vw,1.25rem);font-weight:600;margin-bottom:8px;letter-spacing:-0.01em;color:var(--text)}
.pick-card{display:flex;gap:clamp(16px,3vw,32px);padding:28px 32px;border:1px solid var(--border);border-radius:var(--radius-lg);margin-bottom:24px;align-items:flex-start;box-shadow:var(--shadow-sm);transition:all .25s;position:relative;overflow:hidden;background:var(--bg)}
.pick-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-2px)}
.pick-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--primary);border-radius:0 4px 4px 0}
.pick-card .rank{flex-shrink:0;width:44px;height:44px;background:var(--primary);color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;box-shadow:0 2px 8px rgba(201,138,44,.35)}
.pick-card .rank.budget{background:var(--green)}
.pick-card .rank.upgrade{background:var(--purple)}
.pick-card .info h3{font-family:var(--font-display)}
.pick-card .info .price{color:var(--green);font-weight:600;font-size:.95rem}
.pick-card .info p{color:var(--text-secondary)}
.pick-card .info .badge{background:var(--primary-light);color:var(--primary);font-size:.75rem;font-weight:600;padding:2px 10px;border-radius:100px;text-transform:uppercase;letter-spacing:.04em}
.pick-card .info .badge.budget{background:var(--green-light);color:#065f46}
.pick-card .info .badge.upgrade{background:var(--purple-light);color:#5b21b6}
.grid-3{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}
.cat-card{padding:24px;border:1px solid var(--border);border-radius:var(--radius-md);transition:all .25s;box-shadow:var(--shadow-sm);background:var(--bg);position:relative;overflow:hidden}
.cat-card::after{content:'';position:absolute;bottom:0;left:20%;right:20%;height:3px;background:var(--primary);border-radius:3px 3px 0 0;transform:scaleX(0);transition:transform .25s}
.cat-card:hover{box-shadow:var(--shadow-lg);transform:translateY(-4px)}
.cat-card:hover::after{transform:scaleX(1)}
.cat-card .cat-name{font-weight:700;font-size:1.1rem;color:var(--text)}
.cat-card .cat-count{font-size:.85rem;color:var(--text-muted)}
.post-card{padding:20px;border:1px solid var(--border);border-radius:var(--radius-md);box-shadow:var(--shadow-sm);background:var(--bg)}
.post-card:hover{box-shadow:var(--shadow-md)}
.post-card .post-title{font-weight:600;color:var(--text)}
.post-card .post-meta{font-size:.85rem;color:var(--text-muted)}
.section{padding:clamp(40px,6vw,64px) 0}
.section-title{font-size:1.1rem;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.08em;margin-bottom:24px;padding-bottom:12px;border-bottom:3px solid var(--primary)}
.affiliate-banner{background:#fefce8;border:1px solid #fde68a;border-radius:var(--radius-sm);padding:16px 20px;font-size:.85rem;color:#92400e;margin:32px 0;text-align:center}
footer{padding:48px 0;border-top:1px solid var(--border);text-align:center}
footer p{font-size:.85rem;color:var(--text-muted)}
.social{margin-top:16px;display:flex;gap:20px;justify-content:center}
.social a{color:var(--text-muted);text-decoration:none;transition:color .15s}
.social a:hover{color:var(--text)}
.social svg{width:22px;height:22px;fill:currentColor}
.story-section{padding:clamp(40px,6vw,64px) 0;background:var(--bg-alt);border-top:1px solid var(--border)}
.story-section h2{font-size:1.4rem;font-weight:700;margin-bottom:12px;text-align:center}
.story-section p{font-size:1rem;color:var(--text-secondary);line-height:1.7;margin-bottom:12px}
.story-section .trust-item{padding:16px;background:var(--bg);border-radius:var(--radius-md);border:1px solid var(--border);box-shadow:var(--shadow-sm)}
.story-section .trust-item strong{display:block;font-size:.95rem;color:var(--text);margin-bottom:4px}
.story-section .trust-item span{font-size:.85rem;color:var(--text-muted)}
.buy-btn{display:inline-block;padding:10px 24px;background:var(--accent);color:#1f2937;border-radius:8px;font-weight:600;font-size:.95rem;text-decoration:none;box-shadow:0 1px 3px rgba(0,0,0,.12);transition:all .2s}
.buy-btn:hover{background:var(--accent-dark);text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.2);transform:translateY(-1px)}
.hero{background:linear-gradient(180deg,var(--bg-alt),transparent 80%);padding:clamp(48px,8vw,80px) 0 56px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at 20% 50%,rgba(201,138,44,.08),transparent 60%);pointer-events:none}
.hero h1{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.5rem);font-weight:700;letter-spacing:-0.02em;color:var(--text)}
.hero p{font-size:1.1rem;color:var(--text-secondary);max-width:600px}
.lead-capture{background:var(--text);color:#fff;padding:clamp(40px,6vw,64px) 24px;text-align:center}
.lead-capture h2{font-size:1.4rem;color:#fff}
.lead-capture p{font-size:1rem;color:#fff;opacity:.9}
.lead-capture input{padding:12px 16px;border-radius:var(--radius-sm);border:none;font-size:1rem;min-width:220px;box-shadow:0 1px 3px rgba(0,0,0,.1)}
.lead-capture button{padding:12px 28px;background:var(--primary);color:#fff;border:none;border-radius:var(--radius-sm);font-size:1rem;font-weight:600;cursor:pointer}
.lead-capture button:hover{background:var(--primary-dark)}
.cta-banner{background:linear-gradient(135deg,var(--primary),var(--purple));color:#fff;padding:clamp(32px,5vw,48px) 24px;border-radius:var(--radius-lg);text-align:center;margin:32px 0;position:relative;overflow:hidden}
.cta-banner h3{font-size:1.3rem;color:#fff}
.cta-banner p{font-size:.95rem;color:#fff;opacity:.9}
.cta-banner .buy-btn{background:#fff;color:var(--text)}
.cta-banner .buy-btn:hover{background:#f1f5f9}
:focus-visible{outline:2px solid var(--primary);outline-offset:2px}
.skip-link{position:absolute;top:-40px;left:8px;background:var(--primary);color:#fff;padding:8px 16px;z-index:100;font-size:.9rem;transition:top .15s}
.skip-link:focus{top:0}
.hamburger{display:none;background:none;border:none;cursor:pointer;padding:8px;font-size:1.6rem;color:var(--text);font-family:inherit}
@media(max-width:768px){
.hamburger{display:block}
.nav-links{display:none;position:absolute;top:56px;left:0;right:0;background:var(--bg);border-bottom:1px solid var(--border);flex-direction:column;padding:16px 24px;gap:12px;box-shadow:var(--shadow-lg)}
.nav-links.open{display:flex}
.dropdown{width:100%}
.dropdown-menu{position:static;border:none;box-shadow:none;padding:0 0 0 16px;max-height:none}
.dropdown:hover .dropdown-menu{display:none}
.dropdown.open .dropdown-menu{display:block}
.dropdown-btn{width:100%;justify-content:space-between}
}
@media(max-width:640px){.pick-card{flex-direction:column;gap:16px}.grid-3{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important}}
"""

def update_file(filepath):
    html = filepath.read_text(encoding="utf-8")
    # Replace old CSS block (between <style> and </style>)
    import re
    new_html = re.sub(r'<style>.*?</style>', f'<style>{CSS_SHARED}</style>', html, count=1, flags=re.DOTALL)
    
    fixes = [
        ('color:#888', 'color:var(--text-muted)'),
        ('color:#9ca3af', 'color:var(--text-muted)'),
        ('color:#555', 'color:var(--text-secondary)'),
        ('color:#374151', 'color:var(--text)'),
        ('color:#6b7280', 'color:var(--text-secondary)'),
        ('color:#1f2937', 'color:var(--text)'),
        ('color:#2563eb', 'color:var(--primary)'),
        ('color:#92400e', 'color:#92400e'),
    ]
    
    if new_html != html:
        filepath.write_text(new_html, encoding="utf-8")
        return True
    return False

def main():
    docs = Path("docs")
    updated = 0
    
    # Homepage
    hp = docs / "index.html"
    if hp.exists() and update_file(hp):
        updated += 1
        print(f"  Updated: {hp}")
    
    # Category pages
    for niche_dir in sorted(docs.iterdir()):
        if niche_dir.is_dir() and niche_dir.name != "reviews" and niche_dir.name != "assets":
            idx = niche_dir / "index.html"
            if idx.exists() and update_file(idx):
                updated += 1
                print(f"  Updated: {idx}")
    
    print(f"\nDone! Updated {updated} files with premium CSS.")

if __name__ == "__main__":
    main()
