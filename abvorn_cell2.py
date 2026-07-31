### CELL 2
# -*- coding: utf-8 -*-
"""Abvorn v13 — Cell 2: Apex Swarm (Content Engine + Design + Monetization)"""
import shutil, json, re, time, requests, random, hashlib
from datetime import datetime
from pathlib import Path
from html import escape as html_escape
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from pytrends.request import TrendReq

FTC_DISCLOSURE = '''<div class="disclosure"><strong>Disclosure:</strong> Some links are affiliate links. We may earn a commission at no extra cost to you. Your support helps us keep creating expert content.</div>'''

SOCIAL_X = '''<a href="https://x.com/Abvorn" target="_blank" rel="noopener" aria-label="X (Twitter)" style="display:inline-flex;align-items:center;gap:6px;color:inherit;text-decoration:none"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>'''
SOCIAL_INSTAGRAM = '''<a href="https://www.instagram.com/abvorn/" target="_blank" rel="noopener" aria-label="Instagram" style="display:inline-flex;align-items:center;gap:6px;color:inherit;text-decoration:none"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg></a>'''
SOCIAL_TIKTOK = '''<a href="https://www.tiktok.com/@abvorn" target="_blank" rel="noopener" aria-label="TikTok" style="display:inline-flex;align-items:center;gap:6px;color:inherit;text-decoration:none"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg></a>'''

SOCIALS_HTML = f'''<div class="social-links" style="display:flex;gap:var(--space-md);justify-content:center;margin:var(--space-md) 0">
  {SOCIAL_INSTAGRAM}
  {SOCIAL_TIKTOK}
  {SOCIAL_X}
</div>'''

FOOTER_SOCIALS = f'''<div style="margin:var(--space-md) 0">
  <p style="font-size:var(--text-sm);color:var(--clr-mid-gray);margin-bottom:var(--space-sm)">Follow us for the latest reviews and deals</p>
  {SOCIALS_HTML}
</div>'''

COOKIE_CONSENT_SCRIPT = '''<script src="https://cdn.jsdelivr.net/npm/cookieconsent@3/build/cookieconsent.min.js"></script><script>window.addEventListener("load",function(){window.cookieconsent.initialise({"palette":{"popup":{"background":"#000"},"button":{"background":"#5a7d9a"}},"content":{"message":"This site uses cookies for analytics, personalized ads, and affiliate tracking.","dismiss":"Got it!","link":"Learn more","href":"__SITE_BASE_PATH__/privacy.html"}})});</script>'''

AMAZON_AFFILIATE_TAG = "abvorn-20"

def build_amazon_affiliate_url(query):
    """Build an Amazon search URL with our affiliate tag."""
    q = query.replace(' ', '+').replace(',', '')
    return f"https://www.amazon.com/s?k={q}&tag={AMAZON_AFFILIATE_TAG}"

DESIGN_SYSTEM_CSS = '''
:root {
  --clr-black: #0a0a0a; --clr-off-black: #1a1a1a; --clr-dark-gray: #2a2a2a;
  --clr-mid-gray: #666; --clr-light-gray: #e8e8e8; --clr-off-white: #f6f5f2; --clr-white: #ffffff;
  --clr-primary: var(--niche-primary, #1a1a1a); --clr-accent: var(--niche-accent, #c98a2c);
  --clr-success: #2ecc71; --clr-warning: #f8aa25;
  --font-display: 'Libre Franklin', -apple-system, sans-serif; --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --scale-ratio: 1.25;
  --text-xs: calc(1rem / var(--scale-ratio) / var(--scale-ratio)); --text-sm: calc(1rem / var(--scale-ratio));
  --text-base: 1rem; --text-lg: calc(1rem * var(--scale-ratio)); --text-xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio));
  --text-2xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-3xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --text-4xl: calc(1rem * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio) * var(--scale-ratio));
  --space-xs: 0.25rem; --space-sm: 0.5rem; --space-md: 1rem; --space-lg: 2rem; --space-xl: 4rem; --space-2xl: 8rem;
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 16px;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.08); --shadow-md: 0 4px 12px rgba(0,0,0,0.1);
  --shadow-lg: 0 8px 30px rgba(0,0,0,0.12); --shadow-xl: 0 20px 60px rgba(0,0,0,0.15);
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1); --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --duration-fast: 150ms; --duration-base: 300ms; --duration-slow: 500ms;
}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth;font-size:16px}
body{font-family:var(--font-body);font-size:var(--text-base);line-height:1.7;color:var(--clr-off-black);background:var(--clr-white);-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:var(--font-display);line-height:1.2;font-weight:700;color:var(--clr-black)}
h1{font-size:var(--text-4xl);letter-spacing:-0.02em}
h2{font-size:var(--text-2xl);letter-spacing:-0.01em;margin-top:var(--space-xl);margin-bottom:var(--space-md)}
h3{font-size:var(--text-xl);margin-top:var(--space-lg);margin-bottom:var(--space-sm)}
p{margin-bottom:var(--space-lg);max-width:65ch}
a{color:var(--clr-accent);text-decoration:underline;text-underline-offset:2px}
a:hover{opacity:0.8}
.container{width:100%;max-width:1200px;margin:0 auto;padding:0 var(--space-lg)}
@media(max-width:768px){.container{padding:0 var(--space-md)}h1{font-size:var(--text-2xl)}h2{font-size:var(--text-xl)}}
.card{background:var(--clr-white);border:1px solid var(--clr-light-gray);border-radius:var(--radius-md);padding:var(--space-lg);transition:transform var(--duration-base) var(--ease-out),box-shadow var(--duration-base) var(--ease-out)}
.card:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
.btn{display:inline-flex;align-items:center;gap:var(--space-sm);padding:0.75em 1.5em;font-family:var(--font-body);font-weight:600;font-size:var(--text-sm);text-transform:uppercase;letter-spacing:0.05em;text-decoration:none;color:var(--clr-white);background:var(--clr-primary);border:none;border-radius:var(--radius-sm);cursor:pointer;transition:background var(--duration-fast) var(--ease-out),transform var(--duration-fast) var(--ease-spring),box-shadow var(--duration-fast) var(--ease-out)}
.btn:hover{background:var(--clr-accent);transform:scale(1.03);box-shadow:var(--shadow-md)}
.btn:active{transform:scale(0.97)}
.btn--secondary{background:transparent;border:2px solid var(--clr-accent);color:var(--clr-accent)}
.btn--secondary:hover{background:var(--clr-accent);color:var(--clr-white)}
.input{width:100%;padding:0.75em 1em;font-family:var(--font-body);font-size:var(--text-base);color:var(--clr-off-black);background:var(--clr-off-white);border:2px solid transparent;border-radius:var(--radius-sm);transition:border-color var(--duration-fast) var(--ease-out),box-shadow var(--duration-fast) var(--ease-out)}
.input:focus{outline:none;border-color:var(--clr-accent);box-shadow:0 0 0 3px rgba(90,125,154,0.15)}
.header--scrolled{padding:10px 0 !important;background:rgba(0,0,0,0.95) !important;box-shadow:0 2px 20px rgba(0,0,0,0.3);backdrop-filter:blur(10px)}
.product-card{position:relative;display:flex;gap:var(--space-lg);align-items:flex-start;flex-wrap:wrap;padding:var(--space-lg);border:1px solid var(--clr-light-gray);border-radius:var(--radius-md);margin-bottom:var(--space-lg);background:var(--clr-white);transition:box-shadow var(--duration-base) var(--ease-out)}.product-card:hover{box-shadow:var(--shadow-md)}@media(max-width:768px){.product-card{flex-direction:column;padding:var(--space-md)}}.product-card__image-wrapper{position:relative;flex:0 0 280px}@media(max-width:768px){.product-card__image-wrapper{flex:1 1 100%}}.product-card .product-details{flex:1;min-width:250px}.product-card__badge{position:absolute;top:12px;left:12px;font-size:var(--text-xs);font-weight:700;text-transform:uppercase;letter-spacing:0.05em;padding:4px 10px;border-radius:var(--radius-sm);z-index:2;color:#fff}.product-card__badge--top{background:#f8aa25}.product-card__badge--budget{background:#5a7d9a}.product-card__badge--upgrade{background:#c98a2c}.product-card__price{font-size:var(--text-xl);font-weight:700;color:var(--clr-black);margin:var(--space-sm) 0}.product-card__price-as-of{font-size:var(--text-xs);color:var(--clr-mid-gray);margin-bottom:var(--space-sm)}.product-card .btn{background:#f8aa25;color:#fff;font-weight:700;text-transform:none;letter-spacing:0;padding:0.6em 1.2em;border-radius:var(--radius-sm);font-size:var(--text-sm)}.product-card .btn:hover{background:#e09520;transform:none}
.star-rating{display:flex;align-items:center;gap:2px;margin:var(--space-sm) 0}.star{color:var(--clr-warning);font-size:1.1rem;cursor:default}.rating-text{font-size:var(--text-sm);color:var(--clr-mid-gray);margin-left:var(--space-sm)}
.product-card__image,.hero__image{opacity:0;transform:translateY(20px);transition:opacity 0.6s var(--ease-out),transform 0.6s var(--ease-out)}
.product-card__image.revealed,.hero__image.revealed{opacity:1;transform:translateY(0)}
.sticky-cta{position:fixed;bottom:0;left:0;width:100%;background:rgba(0,0,0,0.95);padding:12px 20px;display:flex;justify-content:space-between;align-items:center;z-index:9998;backdrop-filter:blur(10px);border-top:2px solid var(--clr-accent);transform:translateY(100%);transition:transform var(--duration-base) var(--ease-out)}
.sticky-cta.visible{transform:translateY(0)}
.sticky-cta__text{color:#fff;font-weight:600;font-size:var(--text-sm)}
.sticky-cta .btn{font-size:var(--text-xs);padding:0.5em 1em}
@media(min-width:769px){.sticky-cta{display:none}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:0.01ms!important;transition-duration:0.01ms!important}}
@media(prefers-color-scheme:dark){:root{--clr-black:#f0f0f0;--clr-off-black:#e0e0e0;--clr-mid-gray:#999;--clr-light-gray:#333;--clr-off-white:#1a1a1a;--clr-white:#111}body{background:#111;color:#e0e0e0}h1,h2,h3,h4{color:#f0f0f0}.card{background:#1a1a1a;border-color:#333}.input{background:#222;color:#e0e0e0}}
@media(forced-colors:active){.btn{border:2px solid ButtonText}.card{border:1px solid ButtonText}}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
:focus-visible{outline:2px solid var(--clr-accent);outline-offset:2px}
img{max-width:100%;height:auto}
table{width:100%;border-collapse:collapse;margin:var(--space-lg) 0}
th,td{padding:var(--space-sm) var(--space-md);text-align:left;border-bottom:1px solid var(--clr-light-gray)}
th{font-family:var(--font-display);font-weight:700;background:var(--clr-off-white)}
tr:hover{background:var(--clr-off-white)}
blockquote{border-left:4px solid var(--clr-accent);padding:var(--space-md) var(--space-lg);margin:var(--space-lg) 0;background:var(--clr-off-white);font-style:italic}
.faq-item{border:1px solid var(--clr-light-gray);border-radius:var(--radius-md);margin-bottom:var(--space-md);overflow:hidden}
.faq-question{padding:var(--space-md);cursor:pointer;font-weight:600;display:flex;justify-content:space-between;align-items:center;background:var(--clr-off-white)}
.faq-question:hover{background:var(--clr-light-gray)}
.faq-question::after{content:"+";font-size:1.5em;color:var(--clr-accent)}
.faq-question.open::after{content:"-"}
.faq-answer{padding:0 var(--space-md);max-height:0;overflow:hidden;transition:max-height 0.3s var(--ease-out),padding 0.3s var(--ease-out)}
.faq-answer.open{max-height:500px;padding:var(--space-md)}
.post-meta{display:flex;gap:var(--space-md);color:var(--clr-mid-gray);font-size:var(--text-sm);margin-bottom:var(--space-lg);flex-wrap:wrap}
.post-meta span{display:flex;align-items:center;gap:var(--space-xs)}
.author-box{display:flex;gap:var(--space-md);align-items:center;padding:var(--space-lg);background:var(--clr-off-white);border-radius:var(--radius-md);margin:var(--space-xl) 0}
.author-box__avatar{width:60px;height:60px;border-radius:50%;background:var(--clr-accent);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:1.5em}
.related-posts{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--space-lg);margin:var(--space-xl) 0}
.comments-section{max-width:700px}.comment{padding:var(--space-md);border:1px solid var(--clr-light-gray);border-radius:var(--radius-md);margin-bottom:var(--space-sm)}.comment p{margin:var(--space-sm) 0 0;font-size:var(--text-sm)}
/* Chapter navigation */
.chapter-nav{position:sticky;top:80px;z-index:100;background:var(--clr-white);border:1px solid var(--clr-light-gray);border-radius:var(--radius-md);padding:var(--space-md);margin-bottom:var(--space-xl);max-height:calc(100vh-120px);overflow-y:auto}@media(max-width:768px){.chapter-nav{display:none}}.chapter-nav__title{font-family:var(--font-display);font-size:var(--text-sm);font-weight:700;margin-bottom:var(--space-sm);color:var(--clr-black);text-transform:uppercase;letter-spacing:0.05em}.chapter-nav a{display:block;font-size:var(--text-sm);color:var(--clr-mid-gray);text-decoration:none;padding:var(--space-xs) 0;border-left:2px solid transparent;padding-left:var(--space-sm);transition:all var(--duration-fast) var(--ease-out)}.chapter-nav a:hover,.chapter-nav a.active{color:var(--clr-black);border-left-color:var(--clr-accent)}
/* Hero pick (Wirecutter-style executive summary) */
.hero-pick{background:linear-gradient(135deg,var(--clr-off-white),var(--clr-white));border:2px solid var(--clr-light-gray);border-radius:var(--radius-lg);padding:var(--space-xl);margin-bottom:var(--space-xl);text-align:center}@media(max-width:768px){.hero-pick{padding:var(--space-lg)}}.hero-pick__badge{display:inline-block;background:#f8aa25;color:#fff;font-size:var(--text-xs);font-weight:700;text-transform:uppercase;letter-spacing:0.1em;padding:4px 12px;border-radius:var(--radius-sm);margin-bottom:var(--space-md)}.hero-pick h2{font-size:var(--text-2xl);margin-top:0}.hero-pick .price{font-size:var(--text-2xl);font-weight:700;color:var(--clr-black);margin:var(--space-md) 0}.hero-pick .btn{background:#f8aa25;color:#fff;font-weight:700;text-transform:none;letter-spacing:0;padding:0.75em 2em;font-size:var(--text-base);border-radius:var(--radius-sm)}.hero-pick .btn:hover{background:#e09520;transform:none}
'''

MICRO_INTERACTIONS_SCRIPT = '''<script>
(function(){var h=document.querySelector('header');if(h){window.addEventListener('scroll',function(){h.classList.toggle('header--scrolled',window.scrollY>80)},{passive:true})}
var imgs=document.querySelectorAll('.product-card__image,.hero__image');if('IntersectionObserver'in window){var obs=new IntersectionObserver(function(e){e.forEach(function(e){if(e.isIntersecting){e.target.classList.add('revealed');obs.unobserve(e.target)}})},{threshold:0.1});imgs.forEach(function(i){obs.observe(i)})}else{imgs.forEach(function(i){i.classList.add('revealed')})}
var bar=document.createElement('div');bar.className='reading-progress';bar.style.cssText='position:fixed;top:0;left:0;height:3px;background:var(--clr-accent);z-index:9999;width:0%;transition:width 0.1s';document.body.prepend(bar);
window.addEventListener('scroll',function(){var s=window.scrollY;var h=document.documentElement.scrollHeight-window.innerHeight;bar.style.width=(h>0?(s/h)*100:0)+'%'},{passive:true})
var sc=document.querySelector('.sticky-cta');if(sc){window.addEventListener('scroll',function(){sc.classList.toggle('visible',window.scrollY>600)},{passive:true})}
var stars=document.querySelectorAll('.star');stars.forEach(function(s){s.addEventListener('mouseenter',function(){this.style.animation='star-pulse 0.3s var(--ease-spring)'})});var style=document.createElement('style');style.textContent='@keyframes star-pulse{0%{transform:scale(1)}50%{transform:scale(1.3)}100%{transform:scale(1)}}';document.head.appendChild(style);
var faqs=document.querySelectorAll('.faq-question');faqs.forEach(function(q){q.addEventListener('click',function(){this.classList.toggle('open');var a=this.nextElementSibling;a.classList.toggle('open')})})
})();
</script>'''

RELATED_LINKS_SCRIPT = '''<script>
(async function(){try{var path=window.location.pathname.replace(window.location.origin,'').replace(/^\\/+|\\/+$/g,'').split('/').filter(Boolean);var slug=path[0];if(!slug)return;var resp=await fetch('__SITE_BASE_PATH__/trending.json');var data=await resp.json();var related=data.filter(function(n){return n.slug!==slug}).slice(0,3);var box=document.getElementById('related-posts');if(related.length&&box){box.innerHTML=related.map(function(n){return'<a href="__SITE_BASE_PATH__/'+n.slug+'/" class="card" style="text-decoration:none;color:inherit"><h3 style="margin:0 0 0.5rem">'+n.name+'</h3><p style="margin:0;font-size:0.9rem;color:var(--clr-mid-gray)">Read our guide</p></a>'}).join('')}}catch(e){}})();
</script>'''

# ── ASSET GENERATION ───────────────────────────────────────────────────────
def generate_all_assets_combined(niche_name, products):
    prompt = f"""For the niche '{niche_name}', create a deep brand identity. Products: {json.dumps(products)[:500]}.

Return JSON with:
1. persona: a detailed ideal buyer persona with:
   - name: first name only
   - bio: 1-sentence backstory about them
   - age_range: "25-40"
   - occupation: job title
   - income_level: "budget-conscious" / "mid-range" / "premium"
   - tech_savvy: 1-10
   - goals: what success looks like for them (2-3 items)
   - frustrations: deep frustrations they feel about the problem this niche solves (2-3 items)
   - fears: what they're afraid will happen if they choose wrong (2-3 items)
   - desires: what they secretly wish existed (2-3 items)
   - decision_criteria: how they decide — ["price","quality","reviews","brand","features"]
   - objections: ["it's too expensive", "I don't have time to set it up", etc] (2-3 items)
   - emotional_journey: the transformation arc — from "___" to "___"
   - content_preferences: "detailed guides" / "quick comparisons" / "real stories"
   - tone_of_voice: how to speak to this person

2. theme: design theme {{"primary_color":"#hex","accent_color":"#hex","font_heading":"Playfair Display","font_body":"Inter","blog_title":"Name of Blog"}}

3. keyword: SEO keyword {{"primary_keyword":"best long-tail keyword","search_intent":"commercial"}}

4. persuasion: a content strategy for this niche:
   - core_angle: the single most persuasive angle for this audience
   - trust_builders: ["expert citations", "real testimonials", "data/studies", etc]
   - conversion_barrier: the #1 thing stopping purchases in this niche

Use colors that evoke trust and authority. Primary = bold accent, accent = complementary."""
    result = strict_json(ask_ai(prompt, json_mode=True))
    if not result:
        result = {"persona":{"name":"Alex","bio":"Busy professional looking for quality solutions","age_range":"25-40","occupation":"Professional","income_level":"mid-range","tech_savvy":6,"goals":["Save time","Get value","Feel confident"],"frustrations":["Too many options","Bad quality products","Wasting money"],"fears":["Buying the wrong thing","Getting scammed","Regretting the purchase"],"desires":["A product that just works","Honest reviews","Clear comparison"],"decision_criteria":["quality","reviews","price"],"objections":["Too expensive","Hard to set up","Not sure it'll work"],"emotional_journey":"frustrated to confident","content_preferences":"detailed guides","tone_of_voice":"conversational and honest"},"theme":{"primary_color":"#C0C0C0","accent_color":"#5A7D9A","font_heading":"Playfair Display","font_body":"Inter","blog_title":f"The {niche_name.title()} Insider"},"keyword":{"primary_keyword":f"best {niche_name}","search_intent":"commercial"},"persuasion":{"core_angle":"Solve their biggest frustration","trust_builders":["expert citations","real testimonials","data/studies"],"conversion_barrier":"Trust"}}
    return result

# ── CONTENT STRATEGIST ─────────────────────────────────────────────────────
def content_strategist(state):
    top = sorted(state.get('performance', {}).items(), key=lambda x: x[1].get('conversions',0), reverse=True)[:3]
    prompt = f"""You are the Content Strategist. Current top niches: {json.dumps(top)}. Queue: {state['queue']}.
Decide next action: 'new_niche' (suggest one), 'expand_niche' (add post), or 'optimize' (rewrite low-performing post).
Output JSON: {{"action":"...","target_slug":"...","topic":"...","rationale":"..."}}"""
    d = strict_json(ask_ai(prompt, json_mode=True))
    if not d: return
    if d['action'] == 'new_niche':
        s = d['topic'].replace(" ","_").lower()
        state['queue'].append({"slug":s,"niche":d['topic'],"stage":"products"})
    elif d['action'] == 'expand_niche' and d.get('target_slug'):
        state['queue'].append({"slug":d['target_slug'],"niche":d['target_slug'].replace("_"," ").title(),"stage":"content","topic_hint":d.get('topic')})
    elif d['action'] == 'optimize':
        state['queue'].append({"slug":d['target_slug'],"niche":d['target_slug'].replace("_"," ").title(),"stage":"rewrite"})
    save_state(state)

def discover_trending_products(state):
    """Find REAL trending products people are searching for right now."""
    print("   Trend Engine scanning for hot products...")
    candidates = []
    try:
        pt = TrendReq(hl='en-US', tz=360)
        trends = pt.trending_searches(pn='united_states').head(20)["title"].tolist()
        candidates += [{"source": "google_trends", "text": t} for t in trends]
    except: pass
    try:
        with DDGS() as ddgs:
            for r in ddgs.text("trending products to buy right now 2026", max_results=5):
                candidates.append({"source": "ddgs_general", "text": r['title']})
            for r in ddgs.news("product launch 2026", max_results=5):
                candidates.append({"source": "ddgs_news", "text": r.get('title', '')})
    except: pass
    prompt = f"""From these real-time signals: {json.dumps(candidates[:20])}, identify up to 3 SPECIFIC hot products people are actively searching for.

For each product, identify:
- product_name: exact product name with brand/model (e.g. "Sony WH-1000XM5")
- niche_slug: the niche it belongs to (e.g. "wireless_headphones")
- reason: why this product is trending right now

Return ONLY a JSON array of objects with keys: product_name, niche_slug, reason.
Example: [{{"product_name":"Sony WH-1000XM5","niche_slug":"wireless_headphones","reason":"New model released with better ANC"}}]"""
    products = strict_json(ask_ai(prompt, json_mode=True))
    if not products: return []
    if isinstance(products, dict): products = [products]
    if not isinstance(products, list): return []
    new = []
    for p in products:
        if not isinstance(p, dict): continue
        pname = p.get('product_name', '').strip()
        niche_slug = p.get('niche_slug', '').strip().lower().replace(' ', '_')
        if not pname or not niche_slug: continue
        slug = pname.lower().replace(' ', '_').replace('-', '_')[:50]
        if slug not in state.get('completed',[]) and slug not in state.get('deployed',[]) and slug not in [q['slug'] for q in state.get('queue',[])]:
            new.append({
                "slug": slug, "niche": niche_slug.replace('_', ' ').title(),
                "product_name": pname, "niche_slug": niche_slug,
                "stage": "trending_product"
            })
    state.setdefault('performance', {}).setdefault('TrendEngine', {'total_products_found': len(new)})
    save_state(state)
    print(f"   Found {len(new)} trending product(s): {', '.join(p.get('product_name','?') for p in new)}")
    return new

# ── REAL PRODUCT INFO FROM SEARCH ─────────────────────────────────────────
def find_real_product_info(product_name):
    """Search the web for real product data using DuckDuckGo snippets."""
    info = {"name": product_name, "price": "", "rating": "", "features": [], "pros": [], "cons": [], "summary": "", "source_url": ""}
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{product_name} review price specs", max_results=5))
            if results:
                snippets = "\n".join(f"- {r.get('title','')}: {r.get('body','')[:200]}" for r in results if r.get('body'))
                info['source_url'] = results[0].get('href', '')
                ask = ask_ai(f"Extract real product info from these search snippets about '{product_name}'. Snippets:\n{snippets}\n\nReturn JSON: {{\"price\":\"...\",\"rating\":\"...\",\"features\":[\"...\"],\"pros\":[\"...\"],\"cons\":[\"...\"],\"summary\":\"...\"}}", json_mode=True)
                if ask:
                    if ask.get('price'): info['price'] = ask['price']
                    if ask.get('rating'): info['rating'] = ask['rating']
                    if ask.get('features'): info['features'] = ask['features'] if isinstance(ask['features'], list) else [ask['features']]
                    if ask.get('pros'): info['pros'] = ask['pros'] if isinstance(ask['pros'], list) else [ask['pros']]
                    if ask.get('cons'): info['cons'] = ask['cons'] if isinstance(ask['cons'], list) else [ask['cons']]
                    if ask.get('summary'): info['summary'] = ask['summary']
    except Exception as e:
        logger.warning(f"Failed to get real product info for {product_name}: {e}")
    return info

def query_persuasion_knowledge(niche_name, product_name, persona):
    """Query the General of Persuasion's knowledge for content frameworks and persuasion techniques."""
    try:
        query = f"persuasion framework copywriting {niche_name} {product_name} pain points objections social proof"
        ctx_parts = []
        if persona:
            p = f"Persona: {persona.get('name','')}, goals: {persona.get('goals',[])}, frustrations: {persona.get('frustrations',[])}, fears: {persona.get('fears',[])}"
            ctx_parts.append(p)
        # Try General of Persuasion collection first
        try:
            res = library_db.get_or_create_collection("general_persuasion").query(query_texts=[query], n_results=5)
            if res["documents"][0]:
                ctx_parts.append("--- Persuasion Knowledge ---")
                for d, m in zip(res["documents"][0], res["metadatas"][0]):
                    source = m.get('book', 'General') if m else 'General'
                    ctx_parts.append(f"[{source}]: {d[:600]}")
        except Exception:
            # Fall back to main brain
            res = library_db.query(query_texts=[query], n_results=3)
            if res["documents"][0]:
                ctx_parts.append("--- Brain Knowledge ---")
                for d, m in zip(res["documents"][0], res["metadatas"][0]):
                    source = m.get('book', 'Brain') if m else 'Brain'
                    ctx_parts.append(f"[{source}]: {d[:500]}")
        return "\n\n".join(ctx_parts)[:4000]
    except Exception as e:
        logger.warning(f"Persuasion knowledge query failed: {e}")
        return ""

def write_product_spotlight(product_info, niche_name, persona=None, persuasion_knowledge=""):
    """Write a persona-first, problem-solution content piece that converts readers into buyers."""
    pname = product_info.get('name', 'Product')
    price = product_info.get('price', '')
    rating = product_info.get('rating', '')
    features = product_info.get('features', [])
    pros = product_info.get('pros', [])
    cons = product_info.get('cons', [])
    summary = product_info.get('summary', '')
    features_str = ", ".join(features[:5]) if features else ""
    pros_str = ", ".join(pros[:3]) if pros else ""
    cons_str = ", ".join(cons[:3]) if cons else ""

    persona_prompt = ""
    if persona:
        persona_prompt = f"""
YOUR READER — "{persona.get('name','Your Reader')}"
Bio: {persona.get('bio', '')}
Age: {persona.get('age_range', '')}
Occupation: {persona.get('occupation', '')}
Their Deep Frustrations: {json.dumps(persona.get('frustrations', []))}
Their Fears: {json.dumps(persona.get('fears', []))}
Their Secret Desires: {json.dumps(persona.get('desires', []))}
Their Goals: {json.dumps(persona.get('goals', []))}
Their Objections: {json.dumps(persona.get('objections', []))}
How They Decide: {json.dumps(persona.get('decision_criteria', []))}
Emotional Journey: {json.dumps(persona.get('emotional_journey', ''))}
"""

    prompt = f"""You are writing a conversion-focused content piece. Your ONLY job is to turn readers into buyers by making them feel understood, building trust, and showing them exactly why this product solves their problem.

PRODUCT: {pname}
PRICE: {price}
RATING: {rating}
FEATURES: {features_str}
PROS: {pros_str}
CONS: {cons_str}
SUMMARY: {summary}
NICHE: {niche_name}

{persona_prompt}

PERSUASION KNOWLEDGE FROM EXPERT BOOKS:
{persuasion_knowledge[:2500]}

INSTRUCTIONS — Follow these rules EXACTLY:

1. LEAD WITH THE PERSONA'S PROBLEM, NOT THE PRODUCT
   The first 40% of the article is about THEM — their frustration, their struggle, the cost of NOT solving this problem.
   Make them nod and say "this person gets me."

2. BUILD TRUST BEFORE YOU SELL
   Use specificity (real numbers, real scenarios). Show you understand their objections.
   Use social proof mechanisms naturally.

3. INTRODUCE THE PRODUCT AS THE ANSWER
   Only after establishing the problem deeply, present {pname} as the natural solution.
   Connect every feature back to a BENEFIT for THIS specific reader.

4. ADDRESS OBJECTIONS HEAD-ON
   Bring up their hidden objections before they do, then dismantle them with facts.

5. CREATE URGENCY WITHOUT PRESSURE
   Make them feel "if I don't act now, the problem continues" rather than "limited stock!"

6. END WITH A CLEAR, LOW-RISK CTA
   "Check the price" — frame it as investigation, not commitment.

STRUCTURE TO FOLLOW (PAS framework):
- PROBLEM: Paint the reader's current painful situation vividly
- AGITATE: Make the pain of staying stuck feel worse than the pain of change
- SOLUTION: Present {pname} as the specific, perfect answer
- PROOF: Social proof, features, specs, testimonials (all connected to their problem)
- OBJECTION HANDLING: Address their specific doubts
- TRANSFORMATION: Paint the "after" picture — what their life looks like with this solved
- CALL TO ACTION: Clear, specific, low-friction next step

TONE: {persona.get('tone_of_voice', 'conversational and honest')} — like a knowledgeable friend who's been through the same struggle.

SEO: Naturally include primary keywords "{pname}" and "{pname} review" without keyword stuffing.

Return JSON:
{{{{
  "post_title": "Problem-focused title that grabs attention (50-65 chars) — e.g. 'Stop Wasting Money on Bad [Product]: Why {pname} Actually Works'",
  "meta_description": "Compelling meta (150-160 chars) addressing the core pain",
  "intro": "2-3 sentence hook paragraph (HTML) — leads with the problem/empathy",
  "article_html": "Full article body HTML following the PAS structure above (800-1500 words). Each section must advance the emotional journey: problem → trust → solution → proof → action. AFFILIATE LINKS: Include exactly 2-3 natural affiliate links within the article body text (not just a button). Use the format: <a href=\'https://www.amazon.com/s?k=PRODUCTNAME&tag=abvorn-20\' rel=\'nofollow sponsored\' target=\'_blank\'>check price on Amazon</a>. Integrate them contextually — like \'you can check the current price on Amazon here\' or \'read verified buyer reviews on Amazon\'. Make them feel like helpful resources, not ads.",
  "tags": ["{niche_name}", "{pname}", "buying guide", "honest review"],
  "lead_magnet_title": "Checklist for {pname} buyers",
  "lead_magnet_description": "What to check before you buy"
}}}}"""
    result = strict_json(ask_ai(prompt, json_mode=True))
    return result

# ── QUALITY SELF-ASSESSMENT ────────────────────────────────────────────────
def evaluate_content_quality(post_title, article_html, persona, product_info):
    """AI rates the content on 5 conversion-critical dimensions. Returns score + improvement tips."""
    prompt = f"""You are a conversion copywriting auditor. Rate this content piece on 5 dimensions (1-10 each).

TITLE: {post_title[:100]}
TARGET READER: {json.dumps(persona.get('name', 'Unknown'))}
PAIN POINTS: {json.dumps(persona.get('frustrations', []))}
FEARS: {json.dumps(persona.get('fears', []))}
DESIRES: {json.dumps(persona.get('desires', []))}
OBJECTIONS: {json.dumps(persona.get('objections', []))}
PRODUCT: {json.dumps(product_info.get('name', 'Unknown'))}

CONTENT (first 2000 chars):
{article_html[:2000]}

Rate each dimension:
1. conversion_potential — Does this make the reader genuinely want to buy? Does it address the core desire?
2. specificity — Are there real numbers, specific scenarios, concrete examples? Or is it vague?
3. emotional_arc — Does it take the reader on a journey? Problem → hope → confidence → action?
4. trust_signals — Does it build trust through honesty, social proof, addressing objections, authority?
5. readability — Is it scannable, well-structured, at the right reading level for this persona?

Return JSON:
{{{{
  "conversion_potential": <1-10>,
  "specificity": <1-10>,
  "emotional_arc": <1-10>,
  "trust_signals": <1-10>,
  "readability": <1-10>,
  "overall": <average as float>,
  "strengths": ["top strength 1", "top strength 2"],
  "weaknesses": ["top weakness 1", "top weakness 2"],
  "improvement_tip": "one actionable suggestion to improve this piece"
}}}}"""
    result = strict_json(ask_ai(prompt, json_mode=True))
    return result if result else {"conversion_potential":5,"specificity":5,"emotional_arc":5,"trust_signals":5,"readability":5,"overall":5.0,"strengths":[],"weaknesses":[],"improvement_tip":""}

# ── COMPOUND LEARNING — FEED SUCCESS BACK TO CAPTAINS ─────────────────────
def feed_content_back_to_captains(niche_name, product_name, article_html, quality_score, persona):
    """Store high-performing content patterns into Captain knowledge for future improvement."""
    if quality_score < 7.0:
        return  # Only learn from great content
    try:
        excerpt = article_html[:1500]
        lesson = f"[CONTENT PATTERN] Niche: {niche_name} | Product: {product_name} | Score: {quality_score}/10\n"
        lesson += f"Persona: {persona.get('name', 'Unknown')} — frustrations: {json.dumps(persona.get('frustrations', []))}\n"
        lesson += f"What worked: {excerpt}\n"
        lesson += f"Lesson: This content scored {quality_score}/10 because it addressed {persona.get('name', 'the reader')}'s core frustrations"
        lesson += f" ({json.dumps(persona.get('frustrations', [])[:1])}) and used the PAS framework effectively."
        try:
            # Store in Captain-level knowledge for the niche
            col_name = f"captain_{niche_name.replace(' ', '_').lower()[:20]}"
            collection = library_db.get_or_create_collection(col_name)
            collection.add(
                documents=[lesson],
                metadatas=[{"book": f"Abvorn-{niche_name}", "type": "content_pattern", "score": quality_score}],
                ids=[f"cp_{niche_name}_{product_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"]
            )
            # Also store in General of Persuasion's collection for cross-niche learning
            try:
                gp_col = library_db.get_or_create_collection("general_persuasion")
                gp_col.add(
                    documents=[f"[CONTENT WIN] {niche_name} | {product_name}: {lesson[:800]}"],
                    metadatas=[{"book": f"Abvorn-{niche_name}", "type": "content_win", "score": quality_score}],
                    ids=[f"cw_{niche_name}_{product_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"]
                )
            except Exception:
                pass
            print(f"   📚 Captain learned from {niche_name} (score: {quality_score}/10)")
        except Exception:
            pass
    except Exception:
        pass

def get_niche_state(niche_folder, niche_slug):
    """Load or initialize niche maturity state."""
    state_file = niche_folder / "niche_state.json"
    default = {
        "maturity_level": "seed",
        "total_posts": 0,
        "used_angles": [],
        "content_history": [],
        "avg_quality_score": 0.0,
        "quality_scores": [],
        "last_post_date": None,
        "ndc_results": {}
    }
    if state_file.exists():
        try:
            saved = json.loads(state_file.read_text())
            for k in default:
                saved.setdefault(k, default[k])
            return saved
        except Exception:
            pass
    return dict(default)

def save_niche_state(niche_folder, state_data):
    """Persist niche state to disk."""
    try:
        (niche_folder / "niche_state.json").write_text(json.dumps(state_data, indent=2))
    except Exception:
        pass

# ── NDC 2.0 INTEGRATION ─────────────────────────────────────────────

def _run_ndc_on_product(product_info: dict, niche_name: str) -> dict:
    """Run NDC 2.0 pipeline (Verdict → CI/EAS/SSI/RV → Questioner) on a single product.

    Returns dict with all formula outputs + questions, or empty dict on failure.
    Writes results to niche_state for persistence across cycles.
    """
    from abvorn.core.verdict import AbvornVerdictEngine
    from abvorn.core.ci import ci_from_product
    from abvorn.core.eas import eas_from_product_data
    from abvorn.core.ssi import silent_signal_index, estimate_mention_frequencies
    from abvorn.core.rv import estimate_regret_velocity
    from abvorn.core.questioner import questioner_agent

    try:
        ve = AbvornVerdictEngine()
        verdict = ve.score_product(niche_name, product_info)
        ci = ci_from_product(verdict['overall'])
        eas = eas_from_product_data(product_info)
        freqs = estimate_mention_frequencies(product_info)
        weights = ve._get_weights(niche_name)
        expert = {c['label']: round(c['weight']*10, 1) for c in weights.values()}
        ssi = silent_signal_index(freqs, expert)
        rv = estimate_regret_velocity({**product_info, 'scores': verdict['breakdown']})
        questions = questioner_agent({'ci': ci, 'eas': eas, 'ssi': ssi, 'rv': rv}, product_info)
        return {
            'verdict_overall': verdict['overall'],
            'verdict_breakdown': verdict['breakdown'],
            'ci': ci, 'eas': eas, 'ssi': ssi, 'rv': rv,
            'questions': questions,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
        logger.warning(f"NDC analysis failed for {product_info.get('name', 'unknown')}: {e}")
        return {}


def _apply_ndc_config(state: dict) -> dict:
    """Apply NDC Learner config changes to global state for real behavior changes.

    Reads state['ndc_config'] and toggles feature flags that affect page building.
    """
    cfg = state.get('ndc_config', {})
    changes = []

    # RPS visibility: if Learner decided to enable by default, set flag
    if cfg.get('rps_enabled_by_default', False):
        state['ndc_flags'] = state.get('ndc_flags', {})
        if not state['ndc_flags'].get('rps_visible', False):
            state['ndc_flags']['rps_visible'] = True
            changes.append("RPS widget enabled by default on all article pages")

    # Content framing: if Learner found a winning framing, store for content engine
    if cfg.get('content_framing'):
        state['ndc_flags']['content_framing'] = cfg['content_framing']
        changes.append(f"Content framing set to: {cfg['content_framing']}")

    # Threshold adjustments
    if cfg.get('rps_threshold_adjustment'):
        state['ndc_flags']['rps_threshold'] = cfg['rps_threshold_adjustment']
        changes.append(f"RPS threshold adjusted: {cfg['rps_threshold_adjustment']}")

    if changes:
        print(f"   [NDC-config] {'; '.join(changes)}")

    return state


# ── ECONOMIC SURPLUS TRACKING ────────────────────────────────────

def track_economic_surplus(state: dict, niche: str, page_type: str, affiliate_links: int = 0):
    """Track value created by the system. Nadella: 'Success is measured by economic surplus.'

    Metrics stored in state['surplus']:
    - pages_generated: total pages built
    - affiliate_links_served: total affiliate links on live pages
    - niches_active: unique niches with content
    - estimated_production_value: imputed cost of equivalent manual production
    """
    state.setdefault('surplus', {
        'pages_generated': 0, 'affiliate_links_served': 0,
        'niches_active': set(), 'estimated_production_value': 0.0,
    })
    s = state['surplus']
    s['pages_generated'] = s.get('pages_generated', 0) + 1
    s['affiliate_links_served'] = s.get('affiliate_links_served', 0) + affiliate_links
    active = set(s.get('niches_active', []))
    active.add(niche)
    s['niches_active'] = list(active)
    # Conservative estimate: $150 per expert article (research + writing time)
    s['estimated_production_value'] = s.get('estimated_production_value', 0) + 150.0
    state['surplus'] = s


# ── NDC CHROMADB KNOWLEDGE BASE ─────────────────────────────────

def _init_ndc_chroma():
    """Initialize local ChromaDB for NDC knowledge persistence and query.

    Creates two collections:
    - ndc_knowledge: per-product NDC formula results, queryable by signal type
    - ndc_experiments: experiment lifecycle tracking with outcomes

    Falls back to no-op if chromadb unavailable.
    """
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        ndc_dir = Path(BOARDROOM_DIR if 'BOARDROOM_DIR' in dir() else '.') / '.ndc_chroma'
        ndc_dir.mkdir(exist_ok=True)
        client = chromadb.PersistentClient(path=str(ndc_dir))
        ef = embedding_functions.DefaultEmbeddingFunction()
        know_db = client.get_or_create_collection("ndc_knowledge", embedding_function=ef)
        exp_db = client.get_or_create_collection("ndc_experiments", embedding_function=ef)
        return know_db, exp_db
    except Exception as e:
        logger.warning(f"NDC ChromaDB unavailable: {e}")
        return None, None


def _ndc_store_product(know_db, entry: dict):
    """Store a single NDC product analysis in ChromaDB."""
    if know_db is None:
        return
    try:
        niche = entry.get('niche', 'unknown')
        product = entry.get('product', 'unknown')
        ndc = entry.get('ndc', {})
        doc = json.dumps(ndc, default=str)
        doc_id = f"{niche}::{product}::{ndc.get('timestamp', 'now')}"
        ci_label = ndc.get('ci', {}).get('classification', {}).get('label', 'neutral')
        eas_shape = ndc.get('eas', {}).get('shape', 'unknown')
        ssi_label = ndc.get('ssi', {}).get('classification', {}).get('label', 'neutral')
        rv_label = ndc.get('rv', {}).get('classification', {}).get('label', 'neutral')
        know_db.add(
            documents=[doc],
            metadatas=[{
                'niche': niche, 'product': product,
                'ci_label': ci_label, 'eas_shape': eas_shape,
                'ssi_label': ssi_label, 'rv_label': rv_label,
                'verdict': ndc.get('verdict_overall', 0),
                'timestamp': ndc.get('timestamp', ''),
            }],
            ids=[doc_id],
        )
    except Exception:
        pass


def _ndc_query_by_signal(know_db, signal_type: str, niche: str = None, limit: int = 10) -> list:
    """Query NDC knowledge base by signal type. Returns matching entries.

    signal_type: 'ci:underrated', 'ci:overrated', 'ssi:blind_spot',
                 'rv:impulse', 'eas:honeymoon', etc.
    """
    if know_db is None:
        return []
    try:
        field, value = signal_type.split(':')
        meta_filter = {field + '_label': value}
        if niche:
            meta_filter['niche'] = niche
        results = know_db.query(
            query_texts=[f"{field}:{value}"],
            n_results=limit,
            where=meta_filter,
        )
        entries = []
        if results and results.get('metadatas'):
            for i, meta in enumerate(results['metadatas'][0]):
                entries.append({
                    'metadata': meta,
                    'document': results['documents'][0][i] if results.get('documents') else '',
                })
        return entries
    except Exception:
        return []


def _ndc_store_experiment(exp_db, experiment: dict):
    """Store experiment in ChromaDB for lifecycle tracking."""
    if exp_db is None:
        return
    try:
        name = experiment.get('name', 'unknown')
        doc = json.dumps(experiment, default=str)
        exp_id = f"exp::{name}::{experiment.get('cycle_added', 'now')}"
        exp_db.add(
            documents=[doc],
            metadatas=[{
                'name': name,
                'status': experiment.get('status', 'designed'),
                'niche': experiment.get('niche', ''),
                'type': experiment.get('type', ''),
                'cycle_added': experiment.get('cycle_added', ''),
            }],
            ids=[exp_id],
        )
    except Exception:
        pass


# ── ANALYTICS BRIDGE ────────────────────────────────────────────

def ingest_page_metrics(niche_slug: str, page_type: str, metrics: dict, state: dict):
    """Ingest real page-level analytics into the NDC feedback loop.

    Called externally (or manually) with GA4 or engagement data.
    Metrics are stored in state['ndc_page_metrics'] and consumed
    by the Learner on the next cycle to replace synthetic outcomes.

    Expected metrics dict:
        views, avg_time_on_page, bounce_rate, affiliate_clicks,
        affiliate_ctr, return_rate_90d (if available)
    """
    state.setdefault('ndc_page_metrics', [])
    entry = {
        'niche': niche_slug,
        'page_type': page_type,
        'metrics': metrics,
        'timestamp': datetime.now().isoformat(),
    }
    state['ndc_page_metrics'].append(entry)
    # Keep last 500
    state['ndc_page_metrics'] = state['ndc_page_metrics'][-500:]
    # If we have enough data per niche, auto-complete matching experiments
    _match_metrics_to_experiments(state, niche_slug, metrics)
    save_state(state)
    print(f"   [Analytics] Stored metrics for {niche_slug}/{page_type}: {len(state['ndc_page_metrics'])} total")


def _match_metrics_to_experiments(state: dict, niche_slug: str, metrics: dict):
    """Auto-complete experiments that match incoming analytics data."""
    for exp in state.get('ndc_experiments', []):
        if exp.get('status') == 'active' and exp.get('niche', '').replace(' ', '-').lower() == niche_slug:
            exp['status'] = 'completed'
            exp['completed_at'] = datetime.now().isoformat()
            exp['outcome'] = {
                'success_criteria_met': metrics.get('affiliate_ctr', 0) > 5,
                'metrics': metrics,
            }
            state.setdefault('ndc_completed_experiments', [])
            state['ndc_completed_experiments'].append(exp)
            print(f"   [Analytics] Experiment auto-completed: {exp.get('name')}")


CONTENT_ANGLE_DEFINITIONS = {
    "problem_solution": {
        "label": "Problem → Solution Spotlight",
        "description": "Lead with a vivid problem the persona faces. Agitate it. Then present the product as the precise answer.",
        "best_for": "single product, early-stage niche"
    },
    "comparison": {
        "label": "Head-to-Head Comparison",
        "description": "Compare this product against alternatives. Honest pros/cons for each. Help the reader decide.",
        "best_for": "established niche with 2+ products covered"
    },
    "how_to": {
        "label": "How-To / Tutorial",
        "description": "Step-by-step guide showing the reader how to achieve their goal using this product.",
        "best_for": "mid-stage niche, product with multiple use cases"
    },
    "listicle": {
        "label": "X Reasons Why",
        "description": "Listicle format: '5 Reasons Why [Product] Is the [Best/Worth It]'. Easy to scan, high shareability.",
        "best_for": "any stage, social media distribution"
    },
    "deep_dive": {
        "label": "Complete Guide / Deep Dive",
        "description": "The definitive resource. Covers everything: features, setup, tips, maintenance, alternatives, FAQ.",
        "best_for": "thriving niche, authority building"
    },
    "case_study": {
        "label": "Story / Case Study",
        "description": "Tell the story of someone like the persona who had the problem and found the solution. Narrative drives trust.",
        "best_for": "mid-stage, high-trust products"
    },
    "objection_buster": {
        "label": "Objection Buster",
        "description": "Directly address the #1 objection holding this persona back. Dismantle it with facts, stories, guarantees.",
        "best_for": "high-price products, skeptical personas"
    },
    "hidden_gem": {
        "label": "Hidden Gem Discovery",
        "description": "Surface an underrated product that deserves more attention. CI-driven: the market is wrong about this one.",
        "best_for": "CI=underrated products, value-focused personas"
    },
    "reality_check": {
        "label": "Reality Check",
        "description": "Call out overrated hype. CI-driven: separate marketing from reality. Builds trust through honest skepticism.",
        "best_for": "CI=overrated products, skeptical personas"
    },
    "blind_spot": {
        "label": "What Nobody Tells You",
        "description": "Highlight a feature the market ignores but actually matters. SSI-driven: this is the silent signal buyers miss.",
        "best_for": "SSI=blind spots, feature-focused niches"
    },
    "regret_proof": {
        "label": "Buy It Once, Buy It Right",
        "description": "Help buyers avoid impulse regret. RV-driven: slow down the purchase decision with long-term thinking.",
        "best_for": "RV=impulse regret, high-price products"
    },
    "seasonal": {
        "label": "Seasonal / Timely",
        "description": "Connect the product to a current event, season, or trend. 'Why [X] is the [Season] Gift Everyone Wants'.",
        "best_for": "any niche, time-sensitive boost"
    }
}

def select_content_angle(niche_name, niche_state, product_name, persona, ndc_results=None):
    """Intelligently pick the next content angle based on niche maturity, past angles, and NDC signals."""
    used = niche_state.get('used_angles', [])
    maturity = niche_state.get('maturity_level', 'seed')
    total = niche_state.get('total_posts', 0)

    # ── NDC-prioritized angles ──
    # If we have NDC data, force a signal-matched angle with 60% probability
    ndc_forced = None
    if ndc_results:
        ci_label = ndc_results.get('ci', {}).get('classification', {}).get('label', '')
        ssi_label = ndc_results.get('ssi', {}).get('classification', {}).get('label', '')
        rv_label = ndc_results.get('rv', {}).get('classification', {}).get('label', '')
        eas_shape = ndc_results.get('eas', {}).get('shape', '')

        signal_map = []
        if ci_label == 'Underrated':      signal_map.append('hidden_gem')
        if ci_label == 'Overrated':        signal_map.append('reality_check')
        if eas_shape == 'honeymoon':       signal_map.append('reality_check')
        if rv_label == 'Impulse Regret':   signal_map.append('regret_proof')
        if rv_label == 'Growing Satisfaction': signal_map.append('hidden_gem')

        ssi_features = ndc_results.get('ssi', {}).get('features', [])
        blind_spots = [f for f in ssi_features if f.get('gap', 0) < -3]
        if blind_spots:
            signal_map.append('blind_spot')

        if signal_map and random.random() < 0.6:
            ndc_forced = random.choice(signal_map)

    # Define recommended angles per maturity level (includes NDC-aware types)
    level_angles = {
        "seed": ["problem_solution", "hidden_gem", "reality_check"],
        "sprout": ["problem_solution", "comparison", "objection_buster", "hidden_gem", "reality_check"],
        "growing": ["problem_solution", "comparison", "how_to", "listicle", "objection_buster",
                     "hidden_gem", "reality_check", "blind_spot", "regret_proof"],
        "thriving": ["problem_solution", "comparison", "how_to", "listicle", "deep_dive",
                      "case_study", "objection_buster", "hidden_gem", "reality_check", "blind_spot", "regret_proof"],
        "evergreen": ["problem_solution", "comparison", "how_to", "listicle", "deep_dive",
                       "case_study", "seasonal", "hidden_gem", "reality_check", "blind_spot", "regret_proof"]
    }

    available = level_angles.get(maturity, ["problem_solution"])

    # If NDC forced an angle and it's available, use it
    if ndc_forced and ndc_forced in available:
        chosen = ndc_forced
        print("   [NDC-signal] angle: %s (%s / %s)" % (chosen, ci_label or 'neutral', rv_label or 'neutral'))
    else:
        # Prefer angles least recently used, or never used
        unused = [a for a in available if a not in used]
        if unused:
            chosen = random.choice(unused)
        else:
            used_order = used[-len(available):] if len(used) >= len(available) else used
            last_used = {}
            for i, a in enumerate(available):
                indices = [j for j, u in enumerate(used_order) if u == a]
                last_used[a] = max(indices) if indices else -1
            chosen = min(last_used, key=last_used.get)

    angle_def = CONTENT_ANGLE_DEFINITIONS.get(chosen, CONTENT_ANGLE_DEFINITIONS["problem_solution"])
    return chosen, angle_def

def get_niche_maturity(total_posts, avg_quality_score):
    """Determine maturity level based on post count and quality."""
    if total_posts >= 10 and avg_quality_score >= 7.5:
        return "evergreen"
    elif total_posts >= 7:
        return "thriving"
    elif total_posts >= 4:
        return "growing"
    elif total_posts >= 2:
        return "sprout"
    return "seed"

# ── PERFORMANCE-WEIGHTED QUEUE ─────────────────────────────────────────────
def score_queue_priority(task, state):
    """Score a queued task from 0-25 for processing priority. Higher = sooner."""
    score = 10  # baseline

    # Trend boost: trending-aligned content should publish fast
    if task.get('stage') == 'trending_product':
        score += 8
    trending = task.get('trending_score', 0)
    if trending:
        score += int(trending * 10)  # up to +10 for strongly trending

    # Niche maturity boost: invest in what's working
    niche_slug = task.get('niche_slug', task.get('slug', ''))
    niche_folder = EMPIRE_DIR / niche_slug
    if niche_folder.exists():
        nstate = get_niche_state(niche_folder, niche_slug)
        total = nstate.get('total_posts', 0)
        avg_q = nstate.get('avg_quality_score', 0)
        # Niches with proven quality get priority
        if avg_q >= 8.0 and total >= 2:
            score += 5
        elif avg_q >= 6.0 and total >= 1:
            score += 3
        # New niches get a small boost to get started
        if total == 0:
            score += 2

        # Time since last post — longer wait = higher priority
        last_date = nstate.get('last_post_date')
        if last_date:
            try:
                days_since = (datetime.now() - datetime.strptime(last_date, '%Y-%m-%d')).days
                score += min(days_since, 5)  # cap at +5
            except Exception:
                pass

    # Content rewrite has lower priority
    if task.get('stage') == 'rewrite':
        score -= 3

    # GA4 analytics boost — real user engagement
    perf = state.get('performance', {})
    pdata = perf.get(niche_slug, {})
    if isinstance(pdata, dict):
        ga4 = pdata.get('ga4_score', 0) or 0
        score += min(int(ga4 / 10), 5)

    return min(max(score, 0), 25)

STALE_DAYS = 90

def check_stale_content(state):
    """Re-queue niches whose newest post is older than STALE_DAYS."""
    requeued = []
    now = datetime.now()
    for slug in list(state.get('deployed', []) or []) + list(state.get('completed', []) or []):
        if not slug: continue
        if slug in [q['slug'] for q in state.get('queue', [])]: continue
        meta_file = (EMPIRE_DIR / slug) / "posts_meta.json"
        if not meta_file.exists(): continue
        try:
            posts = json.loads(meta_file.read_text())
            if not posts: continue
            newest = max(p.get('date', '2000-01-01') for p in posts)
            age = (now - datetime.strptime(newest, '%Y-%m-%d')).days
            if age >= STALE_DAYS:
                state['queue'].append({
                    "slug": slug, "niche": slug.replace('_', ' ').title(),
                    "stage": "content", "rewrite": True,
                    "products": posts[-1].get('products', []) if posts else []
                })
                requeued.append(slug)
                print(f"   \uD83D\uDD04 Stale ({age}d): {slug} \u2014 queued for refresh")
        except: pass
    if requeued:
        save_state(state)
        print(f"   Self-heal: {len(requeued)} stale niche(s) requeued")
    return requeued

# ── COMPARISON TABLE ───────────────────────────────────────────────────────
def build_comparison_table(products):
    rows = ""
    for i, p in enumerate(products):
        cat_icon = {"best_overall": "🏆", "best_value": "💰", "premium_pick": "👑"}
        icon = cat_icon.get(p.get('category', ''), '⭐')
        rows += f'''<tr>
            <td><strong>{i+1}. {html_escape(p.get('name', ''))}</strong></td>
            <td>{html_escape(p.get('price', ''))}</td>
            <td>{icon} {p.get('category', '').replace('_', ' ').title()}</td>
            <td><a href="{html_escape(p.get('affiliate_url', '#'))}" class="btn" target="_blank" rel="nofollow sponsored" style="font-size:var(--text-xs);padding:0.4em 0.8em">Search on Amazon</a></td>
        </tr>'''
    return f'''<h2>Quick Comparison</h2>
<div style="overflow-x:auto"><table><thead><tr><th>Product</th><th>Price</th><th>Category</th><th>Action</th></tr></thead><tbody>{rows}</tbody></table></div>'''

# ── NICHE ROUTING ──────────────────────────────────────────────────────────
def route_or_create_niche(niche_slug, niche_name):
    """Route a product to an existing niche or create a new one. Returns the niche slug, folder, meta_file, and persona."""
    state = load_state()
    slug = niche_slug.strip().lower().replace(' ', '_')
    niche_folder = EMPIRE_DIR / slug
    meta_file = niche_folder / "posts_meta.json"
    assets_file = niche_folder / "assets.json"
    posts_meta = json.loads(meta_file.read_text()) if meta_file.exists() else []
    assets = {}
    if assets_file.exists():
        assets = json.loads(assets_file.read_text())
    if not posts_meta:
        assets = generate_all_assets_combined(niche_name, [{"name": niche_name}])
        theme = assets.get('theme', {})
        blog_title = theme.get("blog_title", niche_name)
        index_html = BLOG_INDEX_TEMPLATE
        index_html = index_html.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
        index_html = index_html.replace('__BLOG_TITLE__', html_escape(blog_title))
        index_html = index_html.replace('__BLOG_TITLE_LOWER__', html_escape(blog_title.lower()))
        index_html = index_html.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{slug}/"))
        index_html = index_html.replace('__POST_LIST__', '<p style="text-align:center;padding:40px;color:#666">Our first review is coming soon.</p>')
        index_html = index_html.replace('__PRIMARY_COLOR__', theme.get("primary_color", "#5A7D9A"))
        index_html = index_html.replace('__ACCENT_COLOR__', theme.get("accent_color", "#C98A2C"))
        index_html = index_html.replace('__YEAR__', str(datetime.now().year))
        index_html = index_html.replace('__SOCIALS__', SOCIALS_HTML)
        index_html = index_html.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
        index_html = index_html.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        niche_folder.mkdir(exist_ok=True)
        (niche_folder / "index.html").write_text(index_html)
        assets_file.write_text(json.dumps(assets, indent=2))
        track_economic_surplus(state, slug, 'niche_created', affiliate_links=0)
        print(f"   Created new niche blog: {slug}")
        if slug not in state.get('deployed', []):
            state.setdefault('completed', []).append(slug)
            save_state(state)
    return slug, niche_folder, meta_file, assets

# ── PRODUCT CARDS HTML ─────────────────────────────────────────────────────
def build_product_html(products, images, performance_scores=None):
    if not products: return ""
    for i, p in enumerate(products):
        if not p.get('image'): p['image'] = images[i] if i < len(images) else (images[0] if images else "https://via.placeholder.com/800x600?text=Product+Image")
    html = ""
    for i, p in enumerate(products):
        img = p.get('image') or (images[i] if i < len(images) else "https://via.placeholder.com/800x600?text=Product+Image")
        url = p.get('affiliate_url', '#')
        features = p.get('features', [])
        badge_map = {"best_overall":"Top Pick","best_value":"Best Value","premium_pick":"Upgrade Pick"}
        badge_cls = {"best_overall":"product-card__badge--top","best_value":"product-card__badge--budget","premium_pick":"product-card__badge--upgrade"}
        cat = p.get('category', '')
        features_html = "<ul>" + "".join(f"<li>{html_escape(f)}</li>" for f in features) + "</ul>" if features else ""
        stars = "".join(f'<span class="star" data-rating="{j}">★</span>' for j in range(1, 6))
        rating = round(4.0 + (3 - i) * 0.3, 1) if i < 3 else 4.0
        badge_text = badge_map.get(cat, 'Top Pick')
        badge_class = badge_cls.get(cat, 'product-card__badge--top')
        price = html_escape(p.get('price', 'Check price'))
        price_date = datetime.now().strftime('%B %d, %Y')
        is_hero = (i == 0 and len(products) > 1)
        if is_hero:
            html += f'''
        <div class="hero-pick" id="product-0">
            <div class="hero-pick__badge">{badge_text}</div>
            <img src="{html_escape(img)}" alt="{html_escape(p.get('name','Product'))}" style="max-width:400px;border-radius:var(--radius-md);margin:0 auto var(--space-md)" width="400" height="300" loading="eager">
            <h2>{html_escape(p.get('name','Product'))}</h2>
            <div class="star-rating" style="justify-content:center">{stars} <span class="rating-text">{rating}/5</span></div>
            <p class="desc" style="max-width:500px;margin:var(--space-md) auto">{html_escape(p.get('description','')[:200])}</p>
            <div class="price" style="font-size:var(--text-2xl);font-weight:700;color:var(--clr-black)">${html_escape(p.get('price',''))}</div>
            <p style="font-size:var(--text-xs);color:var(--clr-mid-gray)">As of {price_date}</p>
            <a href="{html_escape(url)}" class="btn" target="_blank" rel="nofollow sponsored">Check Price on Amazon</a>
        </div>'''
        else:
            html += f'''
        <div class="product-card" id="product-{i}">
            <div class="product-card__image-wrapper">
                <img src="{html_escape(img)}" alt="{html_escape(p.get('name','Product'))}" class="product-card__image" loading="lazy" width="400" height="300">
                <div class="product-card__badge {badge_class}">{badge_text}</div>
            </div>
            <div class="product-details">
                <h3>{html_escape(p.get('name','Product'))}</h3>
                <div class="star-rating">{stars} <span class="rating-text">{rating}/5</span></div>
                <div class="product-card__price">${price}</div>
                <p class="product-card__price-as-of">As of {price_date}</p>
                <p class="desc" style="margin-bottom:var(--space-md)">{html_escape(p.get('description','')[:200])}</p>
                {features_html}
                <a href="{html_escape(url)}" class="btn" target="_blank" rel="nofollow sponsored">Check Price</a>
                <div class="product-reactions" style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
                    <button class="reaction-btn-sm" onclick="toggleProductReaction('prod_{i}','like',this)" style="display:flex;align-items:center;gap:4px;padding:4px 10px;border:1px solid var(--clr-neutral);border-radius:6px;background:var(--clr-white);cursor:pointer;font-size:0.8rem;transition:all 0.2s">👍 <span class="prod-like-{i}">0</span></button>
                    <button class="reaction-btn-sm" onclick="toggleProductReaction('prod_{i}','love',this)" style="display:flex;align-items:center;gap:4px;padding:4px 10px;border:1px solid var(--clr-neutral);border-radius:6px;background:var(--clr-white);cursor:pointer;font-size:0.8rem;transition:all 0.2s">❤️ <span class="prod-love-{i}">0</span></button>
                </div>
            </div>
        </div>'''
    return f'<div class="product-section">{html}</div>'

def force_product_card(products, images, niche_name, hero_image):
    html = f'''<div class="hero" style="background:linear-gradient(135deg,var(--clr-black),var(--clr-dark-gray));color:#fff;padding:80px 0;text-align:center">
        <div class="container"><h1 style="font-size:var(--text-4xl);margin-bottom:var(--space-md)">Best {html_escape(niche_name)}</h1>
        <p style="font-size:var(--text-lg);opacity:0.9;margin:0 auto var(--space-lg)">We tested the top products so you don't have to.</p>
        <img src="{hero_image}" class="hero__image" style="max-width:800px;border-radius:var(--radius-lg);margin:0 auto" alt="Best {html_escape(niche_name)}" width="800" height="600"></div></div>'''
    return html + build_product_html(products, images)

# ── INTER-ARTICLE GRAPH ────────────────────────────────────────────────────
def build_cross_links(niche_name, products, current_slug):
    """Find related products from other deployed niches and build cross-links."""
    state = load_state()
    links = []
    all_slugs = set(state.get('deployed', []) + state.get('completed', []))
    for other_slug in all_slugs:
        if other_slug == current_slug: continue
        meta_file = EMPIRE_DIR / other_slug / "posts_meta.json"
        if not meta_file.exists(): continue
        try:
            posts = json.loads(meta_file.read_text())
            for p in posts:
                other_products = p.get('products', [])
                for op in other_products:
                    for prod in products:
                        pname = prod.get('name', '').lower()[:30]
                        oname = op.lower()[:30]
                        if pname and oname and (pname[:15] in oname or oname[:15] in pname):
                            other_slug_clean = other_slug.replace('_', ' ').title()
                            link = f'<a href="{SITE_BASE_PATH}/{other_slug}/" class="cross-link">See also: {other_slug_clean} guide</a>'
                            if link not in links:
                                links.append(link)
        except: pass
        if len(links) >= 3: break
    return '<p style="margin-top:var(--space-lg)">' + " | ".join(links) + '</p>' if links else ""

# ── CONTENT GENERATION ─────────────────────────────────────────────────────
def get_market_context(niche_name):
    ctx = ""
    try:
        from abvorn.core.tavily import TavilyClient
        from abvorn.core.secrets import load_secrets
        tc = TavilyClient(load_secrets().get("TAVILY_KEY", ""))
        if tc.available:
            data = tc.search(f"{niche_name} buying guide 2025", max_results=5, include_answer=True)
            if data.get("answer"):
                ctx += f"Summary: {data['answer']}\n"
            for r in data.get("results", []):
                ctx += f"- {r.get('title','')}: {r.get('content','')[:300]}\n"
    except: pass
    if not ctx.strip():
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(f"{niche_name} buying guide 2025", max_results=5):
                    ctx += f"- {r['title']}: {r.get('body','')[:200]}\n"
        except: pass
    return ctx[:1500]

def generate_faq(niche_name, products, market_context):
    prompt = f"""For a buying guide about '{niche_name}', generate 3-4 frequently asked questions that buyers typically have.
Products: {json.dumps([p.get('name','') for p in products])}
Market context: {market_context[:500]}

Return JSON array of {{"question":"...","answer":"..."}} objects.
Answers should be helpful, specific, and genuine."""
    result = strict_json(ask_ai(prompt, json_mode=True))
    return result if isinstance(result, list) else []

def generate_genius_content(niche_name, keyword_data, products, images, persona, internal_knowledge, existing_posts_meta, live_url, other_posts, market_context="", captain_guidance=""):
    product_names = [p['name'] for p in products]
    prod_json = json.dumps(products, indent=2)[:2000]
    kw = keyword_data.get('primary_keyword', f"best {niche_name}")
    intent = keyword_data.get('search_intent', 'commercial')

    # Generate FAQ
    faqs = generate_faq(niche_name, products, market_context)
    faq_section = ""
    if faqs:
        faq_section = '<section class="faq-section"><h2>Frequently Asked Questions</h2>' + "".join(f'<div class="faq-item"><div class="faq-question">{html_escape(f["question"])}</div><div class="faq-answer"><p>{html_escape(f["answer"])}</p></div></div>' for f in faqs) + '</section>'

    guidance_section = f"\n\n--- Captain's Strategy Guidance ---\n{captain_guidance[:1500]}\n" if captain_guidance else ""

    prompt = f"""You are writing an expert product review and buying guide for '{niche_name}'.

Products to feature: {prod_json}

{internal_knowledge[:2000]}
{guidance_section}
Write a comprehensive, SEO-optimized article. Include:

1. An engaging introduction that hooks the reader
2. A "Quick Comparison" section before diving into individual reviews
3. Individual sections for each product with honest pros and cons
4. A "Buying Guide" section explaining what to look for
5. The FAQ section below (include it exactly as provided): {faq_section}
6. A strong conclusion with a clear recommendation

Requirements:
- Primary keyword: "{kw}" (use naturally 3-4 times)
- Search intent: {intent}
- Tone: expert but approachable, like a knowledgeable friend
- Length: 1500-2500 words
- Include specific details about features, performance, and value
- Be honest about trade-offs (no product is perfect)

Return JSON with these exact keys:
{{
  "post_title": "SEO-optimized title (50-65 chars)",
  "meta_description": "Compelling meta description (150-160 chars)",
  "intro": "2-3 sentence intro paragraph (HTML)",
  "article_html": "Full article body HTML (excluding intro, including comparison section header, product sections, buying guide, FAQ section, and conclusion). AFFILIATE LINKS: Include exactly 2-3 natural affiliate links within the article body. Use format: <a href=\'https://www.amazon.com/s?k=PRODUCTNAME&tag=abvorn-20\' rel=\'nofollow sponsored\' target=\'_blank\'>check price on Amazon</a>. Integrate them naturally in context.",
  "lead_magnet_title": "Lead magnet title like 'The Ultimate {niche_name} Checklist'",
  "lead_magnet_description": "Short pitch for the lead magnet",
  "tags": ["{niche_name}", "buying guide", "reviews", "best {niche_name}"],
  "socials": {{
    "x": "punchy tweet (max 280 chars)",
    "linkedin": "professional post (max 1300 chars)",
    "pinterest": "keyword-rich description (max 500 chars)",
    "facebook": "conversational post (1-2 paragraphs)"
  }}
}}"""

    result = strict_json(ask_ai(prompt, json_mode=True))
    if not result:
        return None

    # Ensure FAQ section appears exactly once in article_html
    if faq_section:
        html = result.get('article_html', '')
        html = re.sub(r'<section class="faq-section">.*?</section>', '', html, flags=re.DOTALL)
        result['article_html'] = html + faq_section

    result['faqs'] = faqs
    return result

def sanitize_ai_html(raw_html):
    if not raw_html: return ""
    allowed_tags = {'h2','h3','h4','p','ul','ol','li','strong','em','a','br','div','span','table','thead','tbody','tr','th','td','blockquote','section','img'}
    soup = BeautifulSoup(raw_html, 'html.parser')
    for tag in soup.find_all():
        if tag.name not in allowed_tags and tag.name is not None:
            tag.unwrap()
        for attr in list(tag.attrs):
            if attr not in {'href','class','id','rel','target','src','alt','width','height'}:
                del tag[attr]
        if tag.name == 'a':
            tag['rel'] = 'nofollow sponsored'
            tag['target'] = '_blank'
    return str(soup)

def self_reflect_and_store(niche_name, article_html):
    prompt = f"""You just wrote an article about '{niche_name}'. Here is the content (first 1000 chars):
{article_html[:1000]}
What is ONE concept, fact, or claim that you are unsure about or that would benefit from further research?
Respond with JSON: {{"gap": "concept", "suggested_answer": "best understanding"}}"""
    r = strict_json(ask_ai(prompt, json_mode=True))
    if r and r.get('gap'):
        add_memory_fact(r['gap'], r.get('suggested_answer',''), source=f"niche_{niche_name}")
        # Queue a targeted research query for the Brain to investigate next cycle
        state = load_state()
        state.setdefault('research_queue', []).append({
            "question": r['gap'],
            "niche": niche_name,
            "timestamp": datetime.now().isoformat()
        })
        save_state(state)
        print(f"   \uD83E\uDD14 Curiosity gap queued: {r['gap'][:80]}...")

# ── TEMPLATES ──────────────────────────────────────────────────────────────
POST_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__POST_TITLE__ | __BLOG_TITLE__</title>
    <meta name="description" content="__META_DESC__">
    <meta name="keywords" content="__TAGS__">
    <link rel="canonical" href="__CANONICAL__">
    <meta property="og:title" content="__POST_TITLE__">
    <meta property="og:description" content="__META_DESC__">
    <meta property="og:image" content="__HERO_IMAGE__">
    <meta property="og:url" content="__CANONICAL__">
    <meta property="og:type" content="article">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="__POST_TITLE__">
    <meta name="twitter:description" content="__META_DESC__">
    <meta name="twitter:image" content="__HERO_IMAGE__">
    <link rel="icon" type="image/svg+xml" href="__SITE_BASE_PATH__/favicon.svg">
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://m.media-amazon.com">
    <style>__DESIGN_SYSTEM_CSS__</style>
    <script type="application/ld+json">__ARTICLE_SCHEMA__</script>
    <script type="application/ld+json">__PRODUCT_SCHEMA__</script>
    <script type="application/ld+json">__FAQ_SCHEMA__</script>
    <script type="application/ld+json">__BREADCRUMB_SCHEMA__</script>
    __COOKIE_CONSENT__
    __GA_TRACKING__
</head>
<body>
<header style="background:var(--clr-black);border-bottom:4px solid __ACCENT_COLOR__;padding:20px 0;position:sticky;top:0;z-index:999;transition:all 0.3s">
    <div class="container" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-sm)">
        <a href="__SITE_BASE_PATH__/" style="display:flex;align-items:center;gap:var(--space-sm);text-decoration:none;color:#fff">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:40px;width:auto">
        </a>
        <nav style="display:flex;align-items:center;gap:var(--space-md);flex-wrap:wrap">
            <a href="__SITE_BASE_PATH__/" style="color:#fff;text-decoration:none;font-weight:600">Home</a>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:#aaa;text-decoration:none">Contact</a>
            <span style="display:flex;gap:8px">__SOCIALS__</span>
        </nav>
    </div>
</header>

<main class="container" style="padding-top:var(--space-xl);padding-bottom:var(--space-2xl)">
    <nav aria-label="Breadcrumb" style="margin-bottom:var(--space-lg);font-size:var(--text-sm);color:var(--clr-mid-gray)">
        <a href="__SITE_BASE_PATH__/" style="color:var(--clr-accent)">Home</a> &raquo;
        <a href="__SITE_BASE_PATH__/__SLUG__/" style="color:var(--clr-accent)">__BLOG_TITLE__</a> &raquo;
        <span>__POST_TITLE__</span>
    </nav>

    <div class="chapter-nav" id="chapter-nav">
        <div class="chapter-nav__title">In this guide</div>
        __CHAPTER_NAV__
    </div>

    <article>
        <header style="margin-bottom:var(--space-xl)">
            <h1 style="font-size:var(--text-3xl);margin-bottom:var(--space-md)">__POST_TITLE__</h1>
            __META__
            <img src="__HERO_IMAGE__" alt="__POST_TITLE__" class="hero__image" style="width:100%;border-radius:var(--radius-lg);margin-bottom:var(--space-lg)" width="1200" height="800" loading="eager">
        </header>

        __INTRO__

        __COMPARISON_TABLE__

        <div class="product-section">
            __ARTICLE_HTML__
        </div>
    </article>

    <div class="author-box">
        <div class="author-box__avatar">A</div>
        <div><strong>Abvorn Editorial</strong><br><span style="font-size:var(--text-sm);color:var(--clr-mid-gray)">Our team of product researchers and industry experts independently tests and reviews products to help you make smarter buying decisions.</span></div>
    </div>

    <section id="faq-section">__FAQ_SECTION__</section>

    <div class="reaction-bar" style="display:flex;gap:12px;margin:var(--space-xl) 0;padding:var(--space-md) 0;border-top:1px solid var(--clr-neutral);border-bottom:1px solid var(--clr-neutral);flex-wrap:wrap">
        <button class="reaction-btn" onclick="toggleReaction('like',this)" data-type="like" style="display:flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--clr-neutral);border-radius:8px;background:var(--clr-white);cursor:pointer;font-size:0.95rem;transition:all 0.2s" onmouseover="this.style.borderColor='var(--clr-primary)'" onmouseout="this.style.borderColor=''">👍 <span id="post-like-count">0</span></button>
        <button class="reaction-btn" onclick="toggleReaction('love',this)" data-type="love" style="display:flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--clr-neutral);border-radius:8px;background:var(--clr-white);cursor:pointer;font-size:0.95rem;transition:all 0.2s" onmouseover="this.style.borderColor='#e74c3c'" onmouseout="this.style.borderColor=''">❤️ <span id="post-love-count">0</span></button>
        <button onclick="sharePost()" style="display:flex;align-items:center;gap:6px;padding:8px 16px;border:1px solid var(--clr-neutral);border-radius:8px;background:var(--clr-white);cursor:pointer;font-size:0.95rem;transition:all 0.2s" onmouseover="this.style.borderColor='var(--clr-secondary)'" onmouseout="this.style.borderColor=''">🔗 Share</button>
    </div>

    <section id="related-posts" class="related-posts" style="margin-top:var(--space-xl)">
        <h2 style="grid-column:1/-1">Related Guides</h2>
    </section>

    <section class="lead-magnet" style="background:linear-gradient(135deg,var(--clr-accent),var(--clr-primary));color:#fff;padding:var(--space-xl);border-radius:var(--radius-lg);text-align:center;margin:var(--space-xl) 0">
        <h2 style="color:#fff;margin-bottom:var(--space-sm)">__LEAD_MAGNET_TITLE__</h2>
        <p style="margin-bottom:var(--space-lg);opacity:0.9">__LEAD_MAGNET_DESC__</p>
        <form class="email-form" style="display:flex;gap:var(--space-sm);max-width:500px;margin:0 auto;flex-wrap:wrap;justify-content:center">
            <input type="text" class="input" placeholder="Your Name" name="name" style="flex:1;min-width:150px;background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.3)" required aria-label="Your name">
            <input type="email" class="input" placeholder="you@email.com" name="email" style="flex:1;min-width:200px;background:rgba(255,255,255,0.15);color:#fff;border-color:rgba(255,255,255,0.3)" required aria-label="Email address">
            <input type="text" name="website" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off">
            <button type="submit" class="btn" style="background:#fff;color:var(--clr-accent);white-space:nowrap">Get Free Guide</button>
        </form>
        <p style="font-size:var(--text-xs);margin-top:var(--space-sm);opacity:0.7">✓ No spam. Unsubscribe anytime.</p>
    </section>

    <section class="comments-section" style="margin:var(--space-xl) 0">
        <h2>Share Your Thoughts</h2>
        <div class="comment-form" style="display:flex;flex-direction:column;gap:var(--space-sm);max-width:600px;margin-bottom:var(--space-lg)">
            <input type="text" id="comment-name" class="input" placeholder="Your name" aria-label="Your name">
            <textarea id="comment-text" class="input" placeholder="Share your experience with these products..." rows="3" aria-label="Your comment" style="resize:vertical;min-height:80px"></textarea>
            <button class="btn" onclick="submitComment()" style="align-self:flex-start">Post Comment</button>
        </div>
        <div id="comments-list"></div>
    </section>
</main>

<script>
function submitComment(){var n=document.getElementById('comment-name').value.trim();var t=document.getElementById('comment-text').value.trim();if(!n||!t)return;var k='abvorn_comments_'+(window.location.pathname.split('/').filter(Boolean)[0]||'home');var c=JSON.parse(localStorage.getItem(k)||'[]');c.unshift({name:n,text:t,date:new Date().toISOString()});localStorage.setItem(k,JSON.stringify(c));document.getElementById('comment-name').value='';document.getElementById('comment-text').value='';renderComments()}
function renderComments(){var k='abvorn_comments_'+(window.location.pathname.split('/').filter(Boolean)[0]||'home');var c=JSON.parse(localStorage.getItem(k)||'[]');var l=document.getElementById('comments-list');if(!c.length){l.innerHTML='<p style="color:var(--clr-mid-gray)">No comments yet. Be the first to share your thoughts!</p>';return}l.innerHTML=c.map(function(c){return'<div class="comment"><strong>'+c.name+'</strong><span style="color:var(--clr-mid-gray);font-size:var(--text-xs);margin-left:var(--space-sm)">'+new Date(c.date).toLocaleDateString()+'</span><p>'+c.text+'</p></div>'}).join('')}
document.addEventListener('DOMContentLoaded',renderComments);
function toggleReaction(type,btn){var k='abvorn_'+type+'_'+window.location.pathname;var d=JSON.parse(localStorage.getItem(k)||'{"active":false,"count":0}');d.active=!d.active;d.count+=d.active?1:-1;localStorage.setItem(k,JSON.stringify(d));var span=btn.querySelector('span');if(span)span.textContent=d.count;btn.style.borderColor=d.active?(type==='love'?'#e74c3c':'var(--clr-primary)'):'';btn.style.background=d.active?'rgba(90,125,154,0.08)':''}
function sharePost(){var u=window.location.href;if(navigator.share){navigator.share({title:document.title,url:u})}else{navigator.clipboard.writeText(u);var k='abvorn_share_'+window.location.pathname;var d=JSON.parse(localStorage.getItem(k)||'{"count":0}');d.count+=1;localStorage.setItem(k,JSON.stringify(d));alert('Link copied!')}}
function toggleProductReaction(id,type,btn){var k='abvorn_'+type+'_prod_'+id;var d=JSON.parse(localStorage.getItem(k)||'{"active":false,"count":0}');d.active=!d.active;d.count+=d.active?1:-1;localStorage.setItem(k,JSON.stringify(d));var span=btn.querySelector('span');if(span)span.textContent=d.count;btn.style.borderColor=d.active?(type==='love'?'#e74c3c':'var(--clr-primary)'):'';btn.style.background=d.active?'rgba(90,125,154,0.08)':''}
</script>

__STICKY_CTA__

<footer style="background:var(--clr-black);color:var(--clr-mid-gray);padding:var(--space-xl) 0;text-align:center;margin-top:var(--space-2xl)">
    <div class="container">
        <a href="__SITE_BASE_PATH__/" style="display:inline-block;margin-bottom:var(--space-md)">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:30px;width:auto;filter:brightness(0.6)">
        </a>
        __FOOTER_SOCIALS__
        <nav style="margin-top:var(--space-md);display:flex;justify-content:center;flex-wrap:wrap;gap:var(--space-sm)">
            <a href="__SITE_BASE_PATH__/" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Home</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/about.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">About</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/privacy.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Privacy</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Contact</a>
            <span style="color:var(--clr-mid-gray)">·</span>
        </nav>
        <p style="margin-top:var(--space-md);font-size:var(--text-xs)">&copy; __YEAR__ Abvorn. All rights reserved.</p>
    </div>
</footer>

__MICRO_INTERACTIONS__
__RELATED_LINKS_SCRIPT__

<script>
document.querySelectorAll('a[href*="amazon"]').forEach(function(a){a.addEventListener('click',function(){try{gtag('event','affiliate_click',{label:this.textContent.trim(),category:'amazon'})}catch(e){}})});
document.querySelectorAll('.email-form').forEach(function(f){f.addEventListener('submit',function(e){e.preventDefault();var email=this.querySelector('input[name="email"]');if(email&&email.value){try{gtag('event','email_signup',{label:email.value,category:'lead_magnet'})}catch(e){};this.querySelector('button').textContent='Thanks!';this.querySelector('button').disabled=true}})});
</script>
</body>
</html>'''

PAGE_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__PAGE_TITLE__ | __SITE_NAME__</title>
<meta name="description" content="__PAGE_DESC__">
<link rel="canonical" href="__CANONICAL__">
<link rel="icon" href="__SITE_BASE_PATH__/favicon.svg">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>__DESIGN_SYSTEM_CSS__</style>
</head><body>
<header style="background:var(--clr-black);border-bottom:4px solid __ACCENT_COLOR__;padding:20px 0;position:sticky;top:0;z-index:999">
    <div class="container" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-sm)">
        <a href="__SITE_BASE_PATH__/" style="display:flex;align-items:center;gap:var(--space-sm);text-decoration:none;color:#fff">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:40px;width:auto">
        </a>
        <nav style="display:flex;align-items:center;gap:var(--space-md);flex-wrap:wrap">
            <a href="__SITE_BASE_PATH__/" style="color:#fff;text-decoration:none;font-weight:600">Home</a>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:#aaa;text-decoration:none">Contact</a>
            <span style="display:flex;gap:8px">__SOCIALS__</span>
        </nav>
    </div>
</header>
<main class="container" style="padding-top:var(--space-xl);padding-bottom:var(--space-2xl);max-width:800px;margin:0 auto">
    <h1>__PAGE_TITLE__</h1>
    __PAGE_CONTENT__
</main>
<footer style="background:var(--clr-black);color:var(--clr-mid-gray);padding:var(--space-xl) 0;text-align:center;margin-top:var(--space-2xl)">
    <div class="container">
        <a href="__SITE_BASE_PATH__/" style="display:inline-block;margin-bottom:var(--space-md)">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:30px;width:auto;filter:brightness(0.6)">
        </a>
        __FOOTER_SOCIALS__
        <nav style="margin-top:var(--space-md);display:flex;justify-content:center;flex-wrap:wrap;gap:var(--space-sm)">
            <a href="__SITE_BASE_PATH__/" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Home</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/about.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">About</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/privacy.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Privacy</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Contact</a>
            <span style="color:var(--clr-mid-gray)">·</span>
        </nav>
        <p style="margin-top:var(--space-md);font-size:var(--text-xs)">&copy; __YEAR__ Abvorn. All rights reserved.</p>
    </div>
</footer>
</body></html>'''

BLOG_INDEX_TEMPLATE = '''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__BLOG_TITLE__ | Abvorn</title>
<meta name="description" content="Expert reviews and buying guides for __BLOG_TITLE_LOWER__.">
<link rel="canonical" href="__CANONICAL__">
<link rel="icon" href="__SITE_BASE_PATH__/favicon.svg">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>__DESIGN_SYSTEM_CSS__</style>
</head><body>
<header style="background:var(--clr-black);border-bottom:4px solid __ACCENT_COLOR__;padding:20px 0;position:sticky;top:0;z-index:999">
    <div class="container" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--space-sm)">
        <a href="__SITE_BASE_PATH__/" style="display:flex;align-items:center;gap:var(--space-sm);text-decoration:none;color:#fff">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:40px;width:auto">
        </a>
        <nav style="display:flex;align-items:center;gap:var(--space-md);flex-wrap:wrap">
            <a href="__SITE_BASE_PATH__/" style="color:#fff;text-decoration:none;font-weight:600">Home</a>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:#aaa;text-decoration:none">Contact</a>
            <span style="display:flex;gap:8px">__SOCIALS__</span>
        </nav>
    </div>
</header>
<section class="hero" style="background:var(--clr-black);color:var(--clr-white);padding:var(--space-xl) 0;text-align:center">
    <div class="container">
        <p style="font-size:var(--text-sm);color:var(--clr-accent);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:var(--space-sm)">Abvorn Reviews</p>
        <h1 style="font-size:var(--text-4xl);margin-bottom:var(--space-md)">__BLOG_TITLE__</h1>
        <p style="font-size:var(--text-lg);opacity:0.8;max-width:600px;margin:0 auto">Expert reviews. Honest recommendations. Better buying decisions.</p>
    </div>
</section>
<main class="container" style="padding:var(--space-xl) 0">
    __FEATURED_POST__
    <div class="post-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:var(--space-lg);margin-top:var(--space-xl)">
        __POST_LIST__
    </div>
</main>
<footer style="background:var(--clr-black);color:var(--clr-mid-gray);padding:var(--space-xl) 0;text-align:center;margin-top:var(--space-2xl)">
    <div class="container">
        <a href="__SITE_BASE_PATH__/" style="display:inline-block;margin-bottom:var(--space-md)">
            <img src="__SITE_BASE_PATH__/logo.svg" alt="Abvorn" style="max-height:30px;width:auto;filter:brightness(0.6)">
        </a>
        __FOOTER_SOCIALS__
        <nav style="margin-top:var(--space-md);display:flex;justify-content:center;flex-wrap:wrap;gap:var(--space-sm)">
            <a href="__SITE_BASE_PATH__/" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Home</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/about.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">About</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/privacy.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Privacy</a>
            <span style="color:var(--clr-mid-gray)">·</span>
            <a href="__SITE_BASE_PATH__/contact.html" style="color:var(--clr-mid-gray);text-decoration:none;font-size:var(--text-sm)">Contact</a>
            <span style="color:var(--clr-mid-gray)">·</span>
        </nav>
        <p style="margin-top:var(--space-md);font-size:var(--text-xs)">&copy; __YEAR__ Abvorn. All rights reserved.</p>
    </div>
</footer>
</body></html>'''

# ── NICHE PROCESSING ──────────────────────────────────────────────────────
def process_niche(task, state):
    slug, niche_name = task['slug'], task['niche']
    niche_folder = EMPIRE_DIR / slug
    niche_folder.mkdir(exist_ok=True)
    meta_file = niche_folder / "posts_meta.json"
    posts_meta = json.loads(meta_file.read_text()) if meta_file.exists() else []
    is_new_blog = (len(posts_meta) == 0)

    if task.get('stage') == 'start':
        task['stage'] = 'products'
        save_state(state)

    if task.get('stage') == 'products':
        # AI-powered product generation (no scraping)
        ctx = get_market_context(niche_name)
        products = generate_products_for_niche(niche_name, ctx)
        images = fetch_images(niche_name, count=min(len(products) + 1, 5))

        task['products'] = products
        task['images'] = images

        if is_new_blog:
            assets = generate_all_assets_combined(niche_name, products)
            task['persona'] = assets['persona']
            task['theme'] = assets['theme']
            task['keyword_data'] = assets['keyword']
        task['stage'] = 'content'
        save_state(state)

    if task.get('stage') == 'trending_product':
        pname = task.get('product_name', slug.replace('_', ' ').title())
        print(f"   Product spotlight mode: {pname}")
        product_info = find_real_product_info(pname)
        niche_slug = task.get('niche_slug', slug)
        target_niche = niche_slug.replace('_', ' ').title()

        # Route to existing niche or create new blog
        actual_niche_slug, niche_folder, meta_file, niche_assets = route_or_create_niche(niche_slug, target_niche)
        posts_meta = json.loads(meta_file.read_text()) if meta_file.exists() else []
        task['product_info'] = product_info
        task['niche_assets'] = niche_assets
        task['stage'] = 'product_content'
        state['queue'] = [q if q['slug'] != task['slug'] else task for q in state['queue']]
        save_state(state)

    if task.get('stage') == 'product_content':
        product_info = task.get('product_info', {})
        pname = product_info.get('name', slug.replace('_', ' ').title())
        target_niche = task.get('niche', niche_name)
        # Crash-safe: derive actual niche slug from product's assigned niche or fallback
        actual_niche_slug = task.get('niche_slug', slug)
        niche_folder = EMPIRE_DIR / actual_niche_slug
        niche_folder.mkdir(exist_ok=True)
        meta_file = niche_folder / "posts_meta.json"
        posts_meta = json.loads(meta_file.read_text()) if meta_file.exists() else []
        niche_assets = task.get('niche_assets', {})
        if not niche_assets and (niche_folder / "assets.json").exists():
            try: niche_assets = json.loads((niche_folder / "assets.json").read_text())
            except: pass
        persona = niche_assets.get('persona', task.get('persona', {}))
        # Select or evolve persona for this niche
        if not persona:
            persona, persona_id = select_or_evolve_persona(target_niche, [product_info])
        else:
            _, persona_id = select_or_evolve_persona(target_niche, [product_info])
        persona_tone = persona.get('tone_of_voice', 'conversational and honest')
        persona_tags = persona.get('tags', [])
        # Select the best content angle for this niche's maturity
        niche_state = get_niche_state(niche_folder, actual_niche_slug)
        # Pass any existing NDC results for angle selection (previous products in same niche)
        existing_ndc = niche_state.get('ndc_results', {}).get(pname) or \
                       next(iter(niche_state.get('ndc_results', {}).values()), None)
        selected_angle, angle_def = select_content_angle(target_niche, niche_state, pname, persona,
                                                         ndc_results=existing_ndc)
        print(f"   Content angle: {angle_def['label']} ({niche_state['maturity_level']} level)")
        persuasion_knowledge = query_persuasion_knowledge(target_niche, pname, persona)
        brain_knowledge = query_internal_brain(target_niche, pname, persona)
        combined_knowledge = (persuasion_knowledge + "\n\n" + brain_knowledge)[:4000]
        result = write_product_spotlight(product_info, target_niche, persona, combined_knowledge)
        if not result:
            logger.warning(f"Product spotlight failed for {pname}")
            state['failed'].append(slug)
            state['queue'] = [q for q in state['queue'] if q['slug'] != slug]
            save_state(state)
            return

        post_title = result['post_title']
        meta_desc = result['meta_description']
        intro = sanitize_ai_html(result.get('intro', ''))
        article_html = sanitize_ai_html(result.get('article_html', ''))
        tags = result.get('tags', [target_niche, pname])
        lead_magnet_title = result.get('lead_magnet_title', f"Buying Guide for {pname}")
        lead_magnet_desc = result.get('lead_magnet_description', "Get our expert tips.")
        blog_title = target_niche
        theme = {"primary_color": "#C0C0C0", "accent_color": "#5A7D9A", "font_heading": "Playfair Display", "font_body": "Inter", "blog_title": blog_title}

        hero_image = f"https://via.placeholder.com/1200x800?text={quote_plus(pname)}"

        # Build affiliate link for this product
        affiliate_url = build_amazon_affiliate_url(pname)
        product_schema_obj = {
            "name": pname,
            "price": product_info.get('price', 'Check price'),
            "rating": product_info.get('rating', ''),
            "affiliate_url": affiliate_url,
        }
        product_schema = build_product_schema([product_schema_obj])
        post_filename = f"{slug}-review-{datetime.now().strftime('%Y%m%d')}.html"

        date_pub = datetime.now().isoformat()
        article_schema = build_article_schema(post_title, meta_desc, f"{SITE_URL}/{actual_niche_slug}/{post_filename}", hero_image, date_pub)
        breadcrumb_schema = build_breadcrumb_schema([
            ("Home", f"{SITE_URL}/"),
            (blog_title, f"{SITE_URL}/{actual_niche_slug}/"),
            (post_title, f"{SITE_URL}/{actual_niche_slug}/{post_filename}")
        ])

        # Sticky CTA
        sticky_cta = f'''<div class="sticky-cta" aria-label="Purchase link">
            <span class="sticky-cta__text">🔥 {html_escape(pname)} at {html_escape(product_info.get('price', 'Check price'))}</span>
            <a href="{html_escape(affiliate_url)}" class="btn" target="_blank" rel="nofollow sponsored">Check Price</a>
        </div>'''

        rendered = POST_TEMPLATE
        rendered = rendered.replace('__POST_TITLE__', html_escape(post_title))
        rendered = rendered.replace('__META_DESC__', html_escape(meta_desc))
        rendered = rendered.replace('__BLOG_TITLE__', html_escape(blog_title))
        rendered = rendered.replace('__SLUG__', html_escape(actual_niche_slug))
        rendered = rendered.replace('__SITE_NAME__', 'Abvorn')
        rendered = rendered.replace('__TAGS__', html_escape(', '.join(tags)))
        rendered = rendered.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{actual_niche_slug}/{post_filename}"))
        rendered = rendered.replace('__HERO_IMAGE__', html_escape(hero_image))
        rendered = rendered.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
        rendered = rendered.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        rendered = rendered.replace('__SOCIALS__', SOCIALS_HTML)
        rendered = rendered.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
        rendered = rendered.replace('__ARTICLE_SCHEMA__', article_schema)
        rendered = rendered.replace('__PRODUCT_SCHEMA__', product_schema)
        rendered = rendered.replace('__FAQ_SCHEMA__', '{}')
        rendered = rendered.replace('__BREADCRUMB_SCHEMA__', breadcrumb_schema)
        rendered = rendered.replace('__COOKIE_CONSENT__', COOKIE_CONSENT_SCRIPT.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        rendered = rendered.replace('__PRIMARY_COLOR__', theme.get("primary_color", "#C0C0C0"))
        rendered = rendered.replace('__ACCENT_COLOR__', theme.get("accent_color", "#5A7D9A"))
        rendered = rendered.replace('__YEAR__', str(datetime.now().year))
        rendered = rendered.replace('__INTRO__', intro)
        # Chapter nav
        chap_links = '<a href="#product-0">Our Pick</a>'
        if products:
            for idx, prod in enumerate(products):
                if idx == 0: continue
                chap_links += f'<a href="#product-{idx}">{html_escape(prod.get("name","")[:40])}</a>'
        chap_links += '<a href="#faq-section">FAQ</a><a href="#related-posts">Related</a>'
        rendered = rendered.replace('__CHAPTER_NAV__', chap_links)
        rendered = rendered.replace('__COMPARISON_TABLE__', '')
        rendered = rendered.replace('__ARTICLE_HTML__', article_html)
        rendered = rendered.replace('__FAQ_SECTION__', '')
        rendered = rendered.replace('__LEAD_MAGNET_TITLE__', html_escape(lead_magnet_title))
        rendered = rendered.replace('__LEAD_MAGNET_DESC__', html_escape(lead_magnet_desc))
        rendered = rendered.replace('__STICKY_CTA__', sticky_cta)
        rendered = rendered.replace('__MICRO_INTERACTIONS__', MICRO_INTERACTIONS_SCRIPT)
        rendered = rendered.replace('__RELATED_LINKS_SCRIPT__', RELATED_LINKS_SCRIPT.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        if GA4_MEASUREMENT_ID:
            rendered = rendered.replace('__GA_TRACKING__', f'<script async src="https://www.googletagmanager.com/gtag/js?id={html_escape(GA4_MEASUREMENT_ID)}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag("js",new Date());gtag("config","{html_escape(GA4_MEASUREMENT_ID)}");</script>')
        else:
            rendered = rendered.replace('__GA_TRACKING__', '')
        rendered = rendered.replace('__META__', f'<div class="post-meta"><span>📅 {datetime.now().strftime("%B %d, %Y")}</span><span>📁 {html_escape(blog_title)}</span><span>📌 {html_escape(pname)}</span></div>')

        post_path = niche_folder / post_filename
        post_path.write_text(rendered)
        print(f"   Wrote product spotlight: {post_filename}")
        track_economic_surplus(state, actual_niche_slug, 'article', affiliate_links=1)

        # ── QUALITY SELF-ASSESSMENT ──
        quality = evaluate_content_quality(post_title, article_html, persona, product_info)
        quality_score = quality.get('overall', 5.0)

        # Record the content angle (selected earlier by select_content_angle)
        niche_state['used_angles'] = niche_state.get('used_angles', [])
        if selected_angle not in niche_state['used_angles']:
            niche_state['used_angles'].append(selected_angle)
        niche_state['total_posts'] = niche_state.get('total_posts', 0) + 1
        niche_state['quality_scores'] = niche_state.get('quality_scores', [])
        niche_state['quality_scores'].append(quality_score)
        niche_state['avg_quality_score'] = sum(niche_state['quality_scores']) / len(niche_state['quality_scores'])
        niche_state['maturity_level'] = get_niche_maturity(niche_state['total_posts'], niche_state['avg_quality_score'])
        niche_state['last_post_date'] = datetime.now().strftime("%Y-%m-%d")
        niche_state['content_history'] = niche_state.get('content_history', [])
        niche_state['content_history'].append({
            "slug": slug, "title": post_title, "angle": selected_angle,
            "quality_score": quality_score, "date": niche_state['last_post_date']
        })
        if len(niche_state['content_history']) > 20:
            niche_state['content_history'] = niche_state['content_history'][-20:]
        save_niche_state(niche_folder, niche_state)

        # ── COMPOUND LEARNING ──
        feed_content_back_to_captains(target_niche, pname, article_html, quality_score, persona)

        # ── PERSONA TRACKING ──
        track_persona_outcome(persona_id, quality_score=quality_score)

        print(f"   🏆 Quality score: {quality_score:.1f}/10 | Niche maturity: {niche_state['maturity_level']} | Angle: {selected_angle}")
        if quality.get('improvement_tip'):
            print(f"   💡 Improvement: {quality['improvement_tip']}")

        # ── NDC 2.0 ANALYSIS ──
        ndc_result = _run_ndc_on_product(product_info, target_niche)
        if ndc_result and ndc_result.get('ci', {}).get('ci') is not None:
            niche_state.setdefault('ndc_results', {})
            niche_state['ndc_results'][pname] = ndc_result
            # Log NDC summary
            ci_signal = ndc_result['ci'].get('classification', {}).get('label', 'neutral')
            eas_shape = ndc_result['eas'].get('shape', 'unknown')
            ssi_label = ndc_result['ssi'].get('classification', {}).get('label', 'neutral')
            rv_label = ndc_result['rv'].get('classification', {}).get('label', 'neutral')
            print(f"   📊 NDC: CI={ci_signal} | EAS={eas_shape} | SSI={ssi_label} | RV={rv_label}")
            if ndc_result['questions']:
                for q in ndc_result['questions'][:2]:
                    print(f"   ❓ Q: {q['question'][:80]}...")
                # Queue questions for the global learning loop
                state.setdefault('ndc_pending_questions', [])
                for q in ndc_result['questions']:
                    state['ndc_pending_questions'].append({
                        'question': q, 'niche': target_niche, 'product': pname,
                        'added': datetime.now().isoformat(),
                    })
                # Keep last 100
                state['ndc_pending_questions'] = state['ndc_pending_questions'][-100:]
                save_state(state)

        # Save post metadata with quality score and persona tracking
        posts_meta.append({
            "title": post_title, "date": datetime.now().strftime("%Y-%m-%d"),
            "file": post_filename, "image": hero_image,
            "meta_description": meta_desc, "tags": tags,
            "products": [pname], "quality_score": quality_score,
            "angle": selected_angle,
            "persona_id": persona_id,
            "persona_name": persona.get('name',''),
            "tone": persona_tone
        })
        meta_file.write_text(json.dumps(posts_meta, indent=2))

        # Update blog index
        post_list_html = ""
        for pm in reversed(posts_meta):
            quality_badge = f'<span style="font-size:0.8rem;color:#888;margin-left:8px">⭐ {pm.get("quality_score", "?"):.1f}</span>' if pm.get('quality_score') else ''
            post_list_html += f'''
            <div class="post-card">
                <a href="{pm['file']}"><img src="{html_escape(pm['image'])}" alt="{html_escape(pm['title'])}" loading="lazy" width="300" height="200"></a>
                <div>
                    <h2><a href="{pm['file']}" style="color:inherit;text-decoration:none">{html_escape(pm['title'])}</a>{quality_badge}</h2>
                    <p>{pm['date']} | Tags: {', '.join(html_escape(t) for t in pm.get('tags',[]))}</p>
                </div>
            </div>'''
        featured_html = ""
        if posts_meta:
            latest = posts_meta[-1]
            featured_html = f'''
        <div class="hero-pick" style="text-align:left;display:flex;gap:var(--space-xl);align-items:center;flex-wrap:wrap">
            <div style="flex:1;min-width:280px">
                <div class="hero-pick__badge">Latest Review</div>
                <h2 style="margin-top:var(--space-sm)"><a href="{latest['file']}" style="color:inherit;text-decoration:none">{html_escape(latest['title'])}</a></h2>
                <p style="color:var(--clr-mid-gray);font-size:var(--text-sm)">{latest['date']} · {', '.join(html_escape(t) for t in latest.get('tags',[])[:3])}</p>
                <p>{html_escape(latest.get('meta_description','')[:200])}</p>
                <a href="{latest['file']}" class="btn" style="background:#f8aa25;text-transform:none;letter-spacing:0">Read Review →</a>
            </div>
            <a href="{latest['file']}" style="flex:0 0 300px"><img src="{html_escape(latest['image'])}" alt="{html_escape(latest['title'])}" style="width:100%;border-radius:var(--radius-md)" width="300" height="200"></a>
        </div>'''
        blog_index = BLOG_INDEX_TEMPLATE
        blog_index = blog_index.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
        blog_index = blog_index.replace('__BLOG_TITLE__', html_escape(blog_title))
        blog_index = blog_index.replace('__BLOG_TITLE_LOWER__', html_escape(blog_title.lower()))
        blog_index = blog_index.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{actual_niche_slug}/"))
        blog_index = blog_index.replace('__FEATURED_POST__', featured_html)
        blog_index = blog_index.replace('__POST_LIST__', post_list_html)
        blog_index = blog_index.replace('__PRIMARY_COLOR__', theme.get("primary_color", "#5A7D9A"))
        blog_index = blog_index.replace('__ACCENT_COLOR__', theme.get("accent_color", "#C98A2C"))
        blog_index = blog_index.replace('__YEAR__', str(datetime.now().year))
        blog_index = blog_index.replace('__SOCIALS__', SOCIALS_HTML)
        blog_index = blog_index.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
        blog_index = blog_index.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        (niche_folder / "index.html").write_text(blog_index)
        track_economic_surplus(state, actual_niche_slug, 'blog_index', affiliate_links=0)

        task['stage'] = 'deployed'
        state['completed'].append(slug)
        state['queue'] = [q for q in state['queue'] if q['slug'] != slug]
        save_state(state)
        print(f"   ✅ Deployed: {slug} → niche: {actual_niche_slug} ({niche_state['maturity_level']} level)")
        return

    if task.get('stage') in ('content', 'rewrite'):
        products = task.get('products', [])
        images = task.get('images', fetch_images(niche_name, 3))
        persona = task.get('persona', {})
        # Select or evolve the persona for this niche
        if not persona:
            persona, persona_id = select_or_evolve_persona(niche_name, products)
        else:
            _, persona_id = select_or_evolve_persona(niche_name, products)
        theme = task.get('theme', {"primary_color":"#C0C0C0","accent_color":"#5A7D9A","font_heading":"Playfair Display","font_body":"Inter","blog_title":niche_name})
        blog_title = theme.get("blog_title", niche_name)
        keyword_data = task.get('keyword_data', {"primary_keyword": f"best {niche_name}", "search_intent": "commercial"})
        # Override keywords with persona-specific ones if available
        persona_keywords = persona.get('keywords', [])
        if persona_keywords:
            keyword_data['primary_keyword'] = persona_keywords[0]
        persona_tags = persona.get('tags', [])
        persona_tone = persona.get('tone_of_voice', 'conversational and honest')
        persona_preferred_formats = persona.get('preferred_formats', [])

        # Build affiliate URLs for each product
        for p in products:
            q = p.get('affiliate_query', p.get('name', niche_name))
            p['affiliate_url'] = build_amazon_affiliate_url(q)

        ctx = get_market_context(niche_name)
        images = images or fetch_images(niche_name, count=3)
        hero_image = images[0] if images else f"https://via.placeholder.com/1200x800?text={quote_plus(niche_name)}"
        internal_knowledge = query_internal_brain(niche_name, keyword_data.get('primary_keyword', niche_name), persona)
        existing_meta = posts_meta[-3:] if posts_meta else []
        live_url = f"{SITE_URL}/{slug}/"

        # Query General/Captain for content strategy guidance
        captain_guidance = ""
        try:
            q = f"What content strategy and persuasion framework should I use for a buying guide about '{niche_name}'? Key products: {[p.get('name','') for p in products[:3]]}"
            guidance, source = captain_query("General of Persuasion", "writing", q)
            if guidance and len(guidance) > 50:
                captain_guidance = f"[Guidance from {source}] {guidance}"
                print(f"   🧠 Captain guidance ({source}): {guidance[:80]}...")
        except Exception as e:
            pass

        content = generate_genius_content(niche_name, keyword_data, products, images, persona, internal_knowledge, existing_meta, live_url, [], market_context=ctx, captain_guidance=captain_guidance)

        if not content:
            logger.warning(f"Content generation failed for {slug}")
            state['failed'].append(slug)
            state['queue'] = [q for q in state['queue'] if q['slug'] != slug]
            save_state(state)
            return

        # Build article HTML
        post_title = content['post_title']
        meta_desc = content['meta_description']
        intro = sanitize_ai_html(content.get('intro', ''))
        article_html = sanitize_ai_html(content.get('article_html', ''))
        cross_links = build_cross_links(niche_name, products, slug)
        if cross_links:
            article_html += cross_links
        tags = content.get('tags', [niche_name])
        # Inject persona-informed tags if available
        if persona_tags:
            for pt in persona_tags:
                if pt not in tags: tags.append(pt)
        lead_magnet_title = content.get('lead_magnet_title', f"Ultimate {niche_name} Checklist")
        lead_magnet_desc = content.get('lead_magnet_description', "Get our expert checklist delivered to your inbox.")

        # Build comparison table
        comparison_table = build_comparison_table(products)

        # Build FAQ section
        faqs = content.get('faqs', [])
        faq_section = ""
        if faqs:
            faq_section = '<section class="faq-section"><h2>Frequently Asked Questions</h2>' + "".join(f'<div class="faq-item"><div class="faq-question">{html_escape(f["question"])}</div><div class="faq-answer"><p>{html_escape(f["answer"])}</p></div></div>' for f in faqs) + '</section>'

        post_filename = f"{slug}-review-{datetime.now().strftime('%Y%m%d')}.html"

        # Build product schema
        product_schema = build_product_schema(products)

        # Build FAQ schema
        faq_schema = build_faq_schema([(f['question'], f['answer']) for f in faqs]) if faqs else '{}'

        # Build breadcrumb schema
        breadcrumb_schema = build_breadcrumb_schema([
            ("Home", f"{SITE_URL}/"),
            (blog_title, f"{SITE_URL}/{slug}/"),
            (post_title, f"{SITE_URL}/{slug}/{post_filename}")
        ])

        # Build article schema
        date_pub = datetime.now().isoformat()
        article_schema = build_article_schema(post_title, meta_desc, f"{SITE_URL}/{slug}/{post_filename}", hero_image, date_pub)

        # Sticky CTA
        sticky_cta = f'''<div class="sticky-cta" aria-label="Quick purchase link">
            <span class="sticky-cta__text">🔥 {html_escape(products[0].get('name', 'Top Pick'))} at {html_escape(products[0].get('price', ''))}</span>
            <a href="{html_escape(products[0].get('affiliate_url', '#'))}" class="btn" target="_blank" rel="nofollow sponsored">Check Price</a>
        </div>'''
        post_path = niche_folder / post_filename

        # Render the post
        rendered = POST_TEMPLATE
        rendered = rendered.replace('__POST_TITLE__', html_escape(post_title))
        rendered = rendered.replace('__META_DESC__', html_escape(meta_desc))
        rendered = rendered.replace('__BLOG_TITLE__', html_escape(blog_title))
        rendered = rendered.replace('__SLUG__', html_escape(slug))
        rendered = rendered.replace('__SITE_NAME__', 'Abvorn')
        rendered = rendered.replace('__TAGS__', html_escape(', '.join(tags)))
        rendered = rendered.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{slug}/{post_filename}"))
        rendered = rendered.replace('__HERO_IMAGE__', html_escape(hero_image))
        rendered = rendered.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
        rendered = rendered.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        rendered = rendered.replace('__ARTICLE_SCHEMA__', article_schema)
        rendered = rendered.replace('__PRODUCT_SCHEMA__', product_schema)
        rendered = rendered.replace('__FAQ_SCHEMA__', faq_schema)
        rendered = rendered.replace('__BREADCRUMB_SCHEMA__', breadcrumb_schema)
        rendered = rendered.replace('__COOKIE_CONSENT__', COOKIE_CONSENT_SCRIPT.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        rendered = rendered.replace('__PRIMARY_COLOR__', theme.get("primary_color","#5A7D9A"))
        rendered = rendered.replace('__ACCENT_COLOR__', theme.get("accent_color","#C98A2C"))
        rendered = rendered.replace('__YEAR__', str(datetime.now().year))
        rendered = rendered.replace('__SOCIALS__', SOCIALS_HTML)
        rendered = rendered.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
        rendered = rendered.replace('__INTRO__', intro)
        rendered = rendered.replace('__COMPARISON_TABLE__', comparison_table)
        rendered = rendered.replace('__ARTICLE_HTML__', article_html)
        rendered = rendered.replace('__FAQ_SECTION__', faq_section)
        rendered = rendered.replace('__LEAD_MAGNET_TITLE__', html_escape(lead_magnet_title))
        rendered = rendered.replace('__LEAD_MAGNET_DESC__', html_escape(lead_magnet_desc))
        rendered = rendered.replace('__STICKY_CTA__', sticky_cta)
        rendered = rendered.replace('__MICRO_INTERACTIONS__', MICRO_INTERACTIONS_SCRIPT)
        rendered = rendered.replace('__RELATED_LINKS_SCRIPT__', RELATED_LINKS_SCRIPT.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
        if GA4_MEASUREMENT_ID:
            rendered = rendered.replace('__GA_TRACKING__', f'<script async src="https://www.googletagmanager.com/gtag/js?id={html_escape(GA4_MEASUREMENT_ID)}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag("js",new Date());gtag("config","{html_escape(GA4_MEASUREMENT_ID)}");</script>')
        else:
            rendered = rendered.replace('__GA_TRACKING__', '')
        rendered = rendered.replace('__META__', f'<div class="post-meta"><span>📅 {datetime.now().strftime("%B %d, %Y")}</span><span>📁 {html_escape(blog_title)}</span><span>📌 {", ".join(html_escape(t) for t in tags[:3])}</span></div>')
        post_path.write_text(rendered)
        print(f"   Wrote: {post_filename}")

        # Write lead magnet page
        lead_html = f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{html_escape(lead_magnet_title)} | Abvorn</title><link rel="icon" href="{SITE_BASE_PATH}/favicon.svg"><style>body{{font-family:'Inter',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f4f4f4;padding:20px}}.card{{background:#fff;padding:40px;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,0.1);max-width:500px;width:100%;text-align:center}}h1{{font-size:1.8rem;margin-bottom:16px}}.btn{{display:inline-block;background:#5A7D9A;color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;font-weight:600;margin-top:16px}}</style></head><body><div class="card"><h1>{html_escape(lead_magnet_title)}</h1><p>{html_escape(lead_magnet_desc)}</p><p style="font-size:0.9rem;color:#666">Enter your email to get instant access.</p><form style="display:flex;flex-direction:column;gap:12px;margin-top:24px"><input type="email" placeholder="you@email.com" required style="padding:12px;border:2px solid #e0e0e0;border-radius:8px;font-size:1rem"><input type="text" name="website" style="position:absolute;left:-9999px" tabindex="-1" autocomplete="off"><button type="submit" class="btn">Get Free Guide</button></form><p style="font-size:0.8rem;color:#999;margin-top:16px">No spam. Unsubscribe anytime.</p></div></body></html>'''
        (niche_folder / "lead-magnet.html").write_text(lead_html)

        # Self-reflection
        self_reflect_and_store(niche_name, article_html)

        # ── QUALITY SELF-ASSESSMENT (legacy content path) ──
        try:
            quality = evaluate_content_quality(post_title, article_html, persona, {"name": products[0].get('name', niche_name)} if products else {})
        except Exception:
            quality = {"overall": 5.0, "improvement_tip": ""}
        quality_score = quality.get('overall', 5.0)
        track_persona_outcome(persona_id, quality_score=quality_score)

        # Update niche state
        niche_state = get_niche_state(niche_folder, slug)
        niche_state['total_posts'] = niche_state.get('total_posts', 0) + 1
        niche_state['quality_scores'] = niche_state.get('quality_scores', [])
        niche_state['quality_scores'].append(quality_score)
        niche_state['avg_quality_score'] = sum(niche_state['quality_scores']) / len(niche_state['quality_scores'])
        niche_state['maturity_level'] = get_niche_maturity(niche_state['total_posts'], niche_state['avg_quality_score'])
        niche_state['last_post_date'] = datetime.now().strftime("%Y-%m-%d")
        save_niche_state(niche_folder, niche_state)

        feed_content_back_to_captains(niche_name, products[0].get('name', niche_name) if products else niche_name, article_html, quality_score, persona)

        # Train the Persuasion General's Captain with this content's patterns
        try:
            if quality_score >= 6.0:
                topics = [f"{niche_name} buying guide strategy", f"persuasion framework for {niche_name}", f"content structure for product reviews"]
                train_captain("General of Persuasion", "writing", topics)
        except Exception:
            pass

        print(f"   🏆 Quality score: {quality_score:.1f}/10 | Niche maturity: {niche_state['maturity_level']}")
        if quality.get('improvement_tip'):
            print(f"   💡 Improvement: {quality['improvement_tip']}")

        # Save post metadata with quality score and persona tracking
        posts_meta.append({
            "title": post_title, "date": datetime.now().strftime("%Y-%m-%d"),
            "file": post_filename, "image": hero_image,
            "meta_description": meta_desc, "tags": tags,
            "products": [p['name'] for p in products],
            "quality_score": quality_score,
            "persona_id": persona_id,
            "persona_name": persona.get('name',''),
            "tone": persona_tone
        })
        meta_file.write_text(json.dumps(posts_meta, indent=2))

        if is_new_blog:
            # Build blog index with quality badges
            post_list_html = ""
            for pm in reversed(posts_meta):
                quality_badge = f'<span style="font-size:0.8rem;color:#888;margin-left:8px">⭐ {pm.get("quality_score", "?"):.1f}</span>' if pm.get('quality_score') else ''
                post_list_html += f'''
                <div class="post-card">
                    <a href="{pm['file']}"><img src="{html_escape(pm['image'])}" alt="{html_escape(pm['title'])}" loading="lazy" width="300" height="200"></a>
                    <div>
                        <h2><a href="{pm['file']}" style="color:inherit;text-decoration:none">{html_escape(pm['title'])}</a>{quality_badge}</h2>
                        <p>{pm['date']} | Tags: {', '.join(html_escape(t) for t in pm.get('tags',[]))}</p>
                    </div>
                </div>'''
            blog_index = BLOG_INDEX_TEMPLATE
            blog_index = blog_index.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
            blog_index = blog_index.replace('__BLOG_TITLE__', html_escape(blog_title))
            blog_index = blog_index.replace('__BLOG_TITLE_LOWER__', html_escape(blog_title.lower()))
            blog_index = blog_index.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{slug}/"))
            featured_html2 = ""
            if posts_meta:
                latest = posts_meta[-1]
                featured_html2 = f'''
        <div class="hero-pick" style="text-align:left;display:flex;gap:var(--space-xl);align-items:center;flex-wrap:wrap">
            <div style="flex:1;min-width:280px">
                <div class="hero-pick__badge">Latest Review</div>
                <h2 style="margin-top:var(--space-sm)"><a href="{latest['file']}" style="color:inherit;text-decoration:none">{html_escape(latest['title'])}</a></h2>
                <p style="color:var(--clr-mid-gray);font-size:var(--text-sm)">{latest['date']} · {', '.join(html_escape(t) for t in latest.get('tags',[])[:3])}</p>
                <p>{html_escape(latest.get('meta_description','')[:200])}</p>
                <a href="{latest['file']}" class="btn" style="background:#f8aa25;text-transform:none;letter-spacing:0">Read Review →</a>
            </div>
            <a href="{latest['file']}" style="flex:0 0 300px"><img src="{html_escape(latest['image'])}" alt="{html_escape(latest['title'])}" style="width:100%;border-radius:var(--radius-md)" width="300" height="200"></a>
        </div>'''
            blog_index = blog_index.replace('__FEATURED_POST__', featured_html2)
            blog_index = blog_index.replace('__POST_LIST__', post_list_html)
            blog_index = blog_index.replace('__PRIMARY_COLOR__', theme.get("primary_color","#5A7D9A"))
            blog_index = blog_index.replace('__ACCENT_COLOR__', theme.get("accent_color","#C98A2C"))
            blog_index = blog_index.replace('__YEAR__', str(datetime.now().year))
            blog_index = blog_index.replace('__SOCIALS__', SOCIALS_HTML)
            blog_index = blog_index.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
            blog_index = blog_index.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
            (niche_folder / "index.html").write_text(blog_index)

            for page_name, page_title, ai_prompt in [
                ("store.html", f"{niche_name.title()} Store", f"Write a short store page for {niche_name}."),
                ("about.html", f"About {blog_title}", f"Write an about page for {blog_title}."),
                ("privacy.html", "Privacy Policy", "<h2>Privacy Policy</h2><p>We respect your privacy.</p>")
            ]:
                page_content = sanitize_ai_html(ask_ai(ai_prompt, use_soul=False)) if "privacy" not in page_title else ai_prompt
                page_html = PAGE_TEMPLATE
                page_html = page_html.replace('__SITE_BASE_PATH__', SITE_BASE_PATH)
                page_html = page_html.replace('__PAGE_TITLE__', html_escape(page_title))
                page_html = page_html.replace('__PAGE_DESC__', html_escape(f"{page_title} | Expert buying guides and reviews"))
                page_html = page_html.replace('__CANONICAL__', html_escape(f"{SITE_URL}/{slug}/{page_name}"))
                page_html = page_html.replace('__SITE_NAME__', html_escape(blog_title))
                page_html = page_html.replace('__PAGE_CONTENT__', page_content)
                page_html = page_html.replace('__PRIMARY_COLOR__', theme.get("primary_color","#5A7D9A"))
                page_html = page_html.replace('__ACCENT_COLOR__', theme.get("accent_color","#C98A2C"))
                page_html = page_html.replace('__YEAR__', str(datetime.now().year))
                page_html = page_html.replace('__SOCIALS__', SOCIALS_HTML)
                page_html = page_html.replace('__FOOTER_SOCIALS__', FOOTER_SOCIALS)
                page_html = page_html.replace('__DESIGN_SYSTEM_CSS__', DESIGN_SYSTEM_CSS.replace('__SITE_BASE_PATH__', SITE_BASE_PATH))
                (niche_folder / page_name).write_text(page_html)

        (niche_folder / "socials.json").write_text(json.dumps(content.get("socials", {}), indent=2))

        # Record prediction for niche futures market
        try:
            expected_conv = max(1, len(products)) * 5
            expected_traffic = random.randint(200, 2000)
            record_prediction(niche_name, expected_conv, expected_traffic, ctx[:200])
        except: pass

        task['stage'] = 'deployed'
        state['completed'].append(slug)
        state['queue'] = [q for q in state['queue'] if q['slug'] != slug]
        save_state(state)
        print(f"   ✅ {slug} deployed — Post: {post_filename} ({niche_state['maturity_level']} level)")

# ── RSS CONTENT REPURPOSING PIPELINE ───────────────────────────────────────
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

def fetch_rss(url):
    """Fetch and parse RSS feed. Returns list of (title, link, summary, pub_date)."""
    items = []
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200: return items
        root = ET.fromstring(resp.content)
        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
        for entry in root.iter("item"):
            title = entry.findtext("title", "")
            link = entry.findtext("link", "")
            desc = entry.findtext("description", "")[:500]
            date = entry.findtext("pubDate", "")[:16]
            content = entry.findtext("content:encoded", "", ns)[:1000]
            body = content or desc
            if title and link:
                items.append((title.strip(), link.strip(), body.strip(), date.strip()))
    except: pass
    return items

def fetch_article_text(url):
    """Fetch article URL and extract readable text via BeautifulSoup."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200: return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script","style","nav","header","footer","aside"]): tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.split("\n") if len(l) > 40]
        return "\n".join(lines[:80])[:5000]
    except: return ""

def repurpose_article(source_title, source_text, niche_name, persona):
    """AI rewrites a source article through Abvorn persona for original content."""
    prompt = f"""You are a product review writer for Abvorn, an affiliate review site. Repurpose the following source material into an ORIGINAL buying guide article about {niche_name}.

Persona: {persona.get('description', 'helpful')}
Tone: {persona.get('tone', 'helpful and informed')}

Rules:
- Write 100% original content — do NOT copy sentences verbatim
- Use our brand voice: confident, helpful, thorough
- Include 2-3 natural affiliate link placements with tag=abvorn-20
- End with a clear recommendation
- Output valid JSON: {{"title":"...","intro":"...","sections":[{{"heading":"...","body":"..."}}],"conclusion":"...","products":[{{"name":"...","description":"..."}}]}}

Source title: {source_title[:200]}
Source content:
{source_text[:3000]}"""
    r = strict_json(ask_ai(prompt, json_mode=True))
    if not r or not r.get('title'): return None
    return r

# ── TRENDING PRODUCT DETECTION ──────────────────────────────────────────────
def trending_products(niche_name, count=5):
    """Get currently trending search terms and product queries for a niche.
    Returns list of (term, score) sorted by trend strength."""
    trending = []
    niche_slug = niche_name.lower().replace(' ', '_')
    # 1. Google Trends — seasonal/recent hot queries
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        kw = niche_name.replace('_', ' ')
        pytrends.build_payload([kw], cat=0, timeframe='now 7-d', geo='', gprop='')
        related = pytrends.related_queries()
        if kw in related and related[kw] is not None:
            top = related[kw]['top']
            if top is not None:
                for _, row in top.head(count).iterrows():
                    t = row.get('query', '')
                    v = int(row.get('value', 0))
                    if t and v:
                        trending.append((t, v / 100.0))
    except: pass
    # 2. Web search — find what's being discussed now with product angle
    try:
        with DDGS() as ddgs:
            # Search for recent product mentions
            for r in ddgs.text(f"best {niche_name} 2025 review", max_results=5):
                t = r.get('title', '')
                if t:
                    trending.append((t, 0.5))
            # Search for trending/model names
            for r in ddgs.text(f"trending {niche_name} products this month", max_results=5):
                t = r.get('title', '')
                if t:
                    trending.append((t, 0.6))
    except: pass
    # Deduplicate and sort
    seen = set()
    unique = []
    for term, score in sorted(trending, key=lambda x: -x[1]):
        key = term.lower()[:40]
        if key not in seen:
            seen.add(key)
            unique.append((term, score))
    return unique[:count]

def score_trend_alignment(article_title, trending_terms):
    """Score how well an article title matches trending terms. Returns 0.0-1.0."""
    if not trending_terms or not article_title: return 0.0
    lower_title = article_title.lower()
    scores = []
    for term, trend_score in trending_terms:
        # Check if trending term keywords appear in the title
        term_words = set(term.lower().split())
        title_words = set(lower_title.split())
        common = term_words & title_words
        if common:
            # Jaccard-like overlap weighted by trend score
            overlap = len(common) / max(len(term_words | title_words), 1)
            scores.append(overlap * trend_score)
        # Check direct substring match
        for word in term_words:
            if word in lower_title and len(word) > 3:
                scores.append(0.3 * trend_score)
                break
    return min(max(scores, default=0), 1.0)

def ingest_rss_sources(state):
    """Process RSS sources filtered by trending products — only repurpose what's hot right now."""
    raw = state.get('rss_sources', [])
    if not raw:
        raw = [
            {"url": "https://www.nytimes.com/wirecutter/feed/", "niche": "wireless_headphones", "label": "Wirecutter"},
            {"url": "https://www.nytimes.com/wirecutter/feed/", "niche": "standing_desk", "label": "Wirecutter"},
            {"url": "https://www.nytimes.com/wirecutter/feed/", "niche": "coffee_maker", "label": "Wirecutter"},
            {"url": "https://www.nytimes.com/wirecutter/feed/", "niche": "air_fryer", "label": "Wirecutter"},
            {"url": "https://www.nytimes.com/wirecutter/feed/", "niche": "treadmill", "label": "Wirecutter"},
            {"url": "https://www.engadget.com/feed/", "niche": "wireless_headphones", "label": "Engadget"},
            {"url": "https://www.engadget.com/feed/", "niche": "webcam", "label": "Engadget"},
            {"url": "https://www.engadget.com/feed/", "niche": "bluetooth_speaker", "label": "Engadget"},
            {"url": "https://www.engadget.com/feed/", "niche": "mechanical_keyboard", "label": "Engadget"},
            {"url": "https://www.engadget.com/feed/", "niche": "laptop_stand", "label": "Engadget"},
            {"url": "https://gizmodo.com/feed", "niche": "robot_vacuum", "label": "Gizmodo"},
            {"url": "https://gizmodo.com/feed", "niche": "air_purifier", "label": "Gizmodo"},
            {"url": "https://gizmodo.com/feed", "niche": "smart_thermostat", "label": "Gizmodo"},
            {"url": "https://gizmodo.com/feed", "niche": "usb_hub", "label": "Gizmodo"},
            {"url": "https://gizmodo.com/feed", "niche": "monitor_arm", "label": "Gizmodo"},
            {"url": "https://www.petmd.com/full/rss", "niche": "dog_food", "label": "PetMD"},
            {"url": "https://www.petmd.com/full/rss", "niche": "cat_tower", "label": "PetMD"},
            {"url": "https://www.petmd.com/full/rss", "niche": "pet_camera", "label": "PetMD"},
            {"url": "https://www.petmd.com/full/rss", "niche": "pet_carrier", "label": "PetMD"},
            {"url": "https://www.petmd.com/full/rss", "niche": "pet_bed", "label": "PetMD"},
            {"url": "https://www.petfoodprocessing.net/rss", "niche": "dog_food", "label": "PetFoodProcessing"},
            {"url": "https://www.petfoodprocessing.net/rss", "niche": "cat_tower", "label": "PetFoodProcessing"},
            {"url": "https://www.catster.com/feed/", "niche": "cat_tower", "label": "Catster"},
            {"url": "https://www.dogster.com/feed", "niche": "dog_food", "label": "Dogster"},
            {"url": "https://www.petlovesbest.com/feed/", "niche": "pet_camera", "label": "PetLovesBest"},
            {"url": "https://www.petlovesbest.com/feed/", "niche": "pet_bed", "label": "PetLovesBest"},
            {"url": "https://www.petlovesbest.com/feed/", "niche": "dog_food", "label": "PetLovesBest"},
            {"url": "https://www.petlovesbest.com/feed/", "niche": "cat_tower", "label": "PetLovesBest"},
            {"url": "https://doglime.com/feed/", "niche": "dog_food", "label": "DogLime"},
            {"url": "https://doglime.com/feed/", "niche": "pet_carrier", "label": "DogLime"},
            {"url": "https://www.vacuumgeek.com/rss/", "niche": "robot_vacuum", "label": "VacuumGeek"},
            {"url": "https://www.vacuumgeek.com/rss/", "niche": "air_purifier", "label": "VacuumGeek"},
            {"url": "https://www.electrokitchen.com/rss/", "niche": "coffee_maker", "label": "ElectroKitchen"},
            {"url": "https://www.electrokitchen.com/rss/", "niche": "air_fryer", "label": "ElectroKitchen"},
            {"url": "https://www.electrokitchen.com/rss/", "niche": "blender", "label": "ElectroKitchen"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "coffee_maker", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "air_fryer", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "blender", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "toaster", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "robot_vacuum", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "washing_machine", "label": "Reviewed"},
            {"url": "https://www.reviewed.com/articles.atom", "niche": "dryer", "label": "Reviewed"},
            {"url": "https://www.goodhousekeeping.com/rss/appliances.xml", "niche": "coffee_maker", "label": "GoodHousekeeping"},
            {"url": "https://www.goodhousekeeping.com/rss/appliances.xml", "niche": "air_fryer", "label": "GoodHousekeeping"},
            {"url": "https://www.goodhousekeeping.com/rss/appliances.xml", "niche": "blender", "label": "GoodHousekeeping"},
            {"url": "https://www.goodhousekeeping.com/rss/appliances.xml", "niche": "toaster", "label": "GoodHousekeeping"},
            {"url": "https://www.goodhousekeeping.com/rss/appliances.xml", "niche": "robot_vacuum", "label": "GoodHousekeeping"},
            {"url": "https://blog.yaleappliance.com/rss.xml", "niche": "coffee_maker", "label": "YaleAppliance"},
            {"url": "https://blog.yaleappliance.com/rss.xml", "niche": "air_fryer", "label": "YaleAppliance"},
            {"url": "https://blog.yaleappliance.com/rss.xml", "niche": "washing_machine", "label": "YaleAppliance"},
            {"url": "https://blog.yaleappliance.com/rss.xml", "niche": "dryer", "label": "YaleAppliance"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "webcam", "label": "TheVerge"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "mechanical_keyboard", "label": "TheVerge"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "laptop_stand", "label": "TheVerge"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "usb_hub", "label": "TheVerge"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "bluetooth_speaker", "label": "TheVerge"},
            {"url": "https://www.theverge.com/rss/index.xml", "niche": "wireless_headphones", "label": "TheVerge"},
            {"url": "https://runningonrealfood.com/feed/", "niche": "coffee_maker", "label": "RunningOnRealFood"},
            {"url": "https://runningonrealfood.com/feed/", "niche": "air_fryer", "label": "RunningOnRealFood"},
            {"url": "https://runningonrealfood.com/feed/", "niche": "blender", "label": "RunningOnRealFood"},
            {"url": "https://runningonrealfood.com/feed/", "niche": "toaster", "label": "RunningOnRealFood"},
            {"url": "https://www.techradar.com/rss", "niche": "webcam", "label": "TechRadar"},
            {"url": "https://www.techradar.com/rss", "niche": "mechanical_keyboard", "label": "TechRadar"},
            {"url": "https://www.techradar.com/rss", "niche": "laptop_stand", "label": "TechRadar"},
            {"url": "https://www.techradar.com/rss", "niche": "bluetooth_speaker", "label": "TechRadar"},
            {"url": "http://feeds.arstechnica.com/arstechnica/index/", "niche": "webcam", "label": "ArsTechnica"},
            {"url": "http://feeds.arstechnica.com/arstechnica/index/", "niche": "mechanical_keyboard", "label": "ArsTechnica"},
            {"url": "http://feeds.arstechnica.com/arstechnica/index/", "niche": "usb_hub", "label": "ArsTechnica"},
            {"url": "https://www.wired.com/feed/rss", "niche": "webcam", "label": "Wired"},
            {"url": "https://www.wired.com/feed/rss", "niche": "bluetooth_speaker", "label": "Wired"},
            {"url": "https://www.wired.com/feed/rss", "niche": "wireless_headphones", "label": "Wired"},
            {"url": "https://venturebeat.com/feed/", "niche": "webcam", "label": "VentureBeat"},
            {"url": "https://venturebeat.com/feed/", "niche": "laptop_stand", "label": "VentureBeat"},
            {"url": "https://petapixel.com/feed/", "niche": "camera", "label": "PetaPixel"},
            {"url": "https://petapixel.com/feed/", "niche": "lens", "label": "PetaPixel"},
            {"url": "https://petapixel.com/feed/", "niche": "tripod", "label": "PetaPixel"},
            {"url": "https://www.thephoblographer.com/feed/", "niche": "camera", "label": "Phoblographer"},
            {"url": "https://www.thephoblographer.com/feed/", "niche": "lens", "label": "Phoblographer"},
            {"url": "https://www.thephoblographer.com/feed/", "niche": "camera_bag", "label": "Phoblographer"},
            {"url": "https://amateurphotographer.com/feed/", "niche": "camera", "label": "AmateurPhotographer"},
            {"url": "https://amateurphotographer.com/feed/", "niche": "lens", "label": "AmateurPhotographer"},
            {"url": "https://amateurphotographer.com/feed/", "niche": "tripod", "label": "AmateurPhotographer"},
            {"url": "https://digital-photography-school.com/feed/", "niche": "camera", "label": "DigPhotoSchool"},
            {"url": "https://digital-photography-school.com/feed/", "niche": "camera_bag", "label": "DigPhotoSchool"},
            {"url": "https://www.england.nhs.uk/feed/", "niche": "fitness_tracker", "label": "NHS"},
            {"url": "https://www.england.nhs.uk/feed/", "niche": "sleep_aid", "label": "NHS"},
            {"url": "https://minimalistbaker.com/feed/", "niche": "cookware_set", "label": "MinimalistBaker"},
            {"url": "https://minimalistbaker.com/feed/", "niche": "knife_set", "label": "MinimalistBaker"},
            {"url": "https://minimalistbaker.com/feed/", "niche": "blender", "label": "MinimalistBaker"},
            {"url": "https://minimalistbaker.com/feed/", "niche": "air_fryer", "label": "MinimalistBaker"},
            {"url": "https://www.cntraveler.com/feed/rss", "niche": "luggage", "label": "CNTraveler"},
            {"url": "https://www.cntraveler.com/feed/rss", "niche": "travel_backpack", "label": "CNTraveler"},
            {"url": "https://thepointsguy.com/feed/", "niche": "luggage", "label": "PointsGuy"},
            {"url": "https://thepointsguy.com/feed/", "niche": "travel_backpack", "label": "PointsGuy"},
            {"url": "https://www.nomadicmatt.com/feed/", "niche": "travel_backpack", "label": "NomadicMatt"},
            {"url": "https://www.nomadicmatt.com/feed/", "niche": "travel_pillow", "label": "NomadicMatt"},
            {"url": "https://www.artnews.com/feed/", "niche": "art_supplies", "label": "ARTnews"},
            {"url": "https://www.thisiscolossal.com/feed/", "niche": "art_supplies", "label": "Colossal"},
            {"url": "https://www.thisiscolossal.com/feed/", "niche": "easel", "label": "Colossal"},
            {"url": "https://mymodernmet.com/feed/", "niche": "art_supplies", "label": "MyModernMet"},
            {"url": "https://mymodernmet.com/feed/", "niche": "easel", "label": "MyModernMet"},
            {"url": "https://mymodernmet.com/feed/", "niche": "paint_brush", "label": "MyModernMet"},
            {"url": "https://hyperallergic.com/feed/", "niche": "art_supplies", "label": "Hyperallergic"},
            {"url": "https://hyperallergic.com/feed/", "niche": "easel", "label": "Hyperallergic"},
            {"url": "https://hyperallergic.com/feed/", "niche": "paint_brush", "label": "Hyperallergic"},
            {"url": "https://www.runnersworld.com/rss/all.xml/", "niche": "running_shoes", "label": "RunnersWorld"},
            {"url": "https://www.runnersworld.com/rss/all.xml/", "niche": "sports_bra", "label": "RunnersWorld"},
            {"url": "https://www.trailrunnermag.com/feed/", "niche": "running_shoes", "label": "TrailRunner"},
            {"url": "https://www.trailrunnermag.com/feed/", "niche": "sports_bra", "label": "TrailRunner"},
            {"url": "https://www.fatherly.com/feed", "niche": "baby_monitor", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "stroller", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "baby_carrier", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "high_chair", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "baby_car_seat", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "diaper_bag", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "bottle_warmer", "label": "Fatherly"},
            {"url": "https://www.fatherly.com/feed", "niche": "baby_bouncer", "label": "Fatherly"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "baby_monitor", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "stroller", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "baby_carrier", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "high_chair", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "baby_car_seat", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "diaper_bag", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "bottle_warmer", "label": "ScaryMommy"},
            {"url": "https://www.scarymommy.com/feed/", "niche": "baby_bouncer", "label": "ScaryMommy"},
            {"url": "https://www.gamespot.com/feeds/news/", "niche": "gaming_headset", "label": "GameSpot"},
            {"url": "https://www.gamespot.com/feeds/news/", "niche": "gaming_mouse", "label": "GameSpot"},
            {"url": "https://www.gamespot.com/feeds/news/", "niche": "gaming_monitor", "label": "GameSpot"},
            {"url": "https://www.pcgamer.com/rss/", "niche": "gaming_headset", "label": "PCGamer"},
            {"url": "https://www.pcgamer.com/rss/", "niche": "gaming_mouse", "label": "PCGamer"},
            {"url": "https://www.pcgamer.com/rss/", "niche": "gaming_chair", "label": "PCGamer"},
            {"url": "https://www.pcgamer.com/rss/", "niche": "gaming_monitor", "label": "PCGamer"},
            {"url": "https://www.rockpapershotgun.com/feed/", "niche": "gaming_headset", "label": "RPS"},
            {"url": "https://www.rockpapershotgun.com/feed/", "niche": "gaming_mouse", "label": "RPS"},
            {"url": "https://www.rockpapershotgun.com/feed/", "niche": "gaming_chair", "label": "RPS"},
            {"url": "https://www.cnet.com/roadshow/news/rss", "niche": "dash_cam", "label": "CNETCars"},
            {"url": "https://www.cnet.com/roadshow/news/rss", "niche": "car_phone_mount", "label": "CNETCars"},
            {"url": "https://www.cnet.com/roadshow/news/rss", "niche": "car_jump_starter", "label": "CNETCars"},
            {"url": "https://www.cnet.com/roadshow/news/rss", "niche": "car_seat_cover", "label": "CNETCars"},
            {"url": "https://www.themiddlesizedgarden.co.uk/feed", "niche": "garden_hose", "label": "MidSizedGarden"},
            {"url": "https://www.themiddlesizedgarden.co.uk/feed", "niche": "pruning_shears", "label": "MidSizedGarden"},
            {"url": "https://www.themiddlesizedgarden.co.uk/feed", "niche": "garden_tools", "label": "MidSizedGarden"},
            {"url": "https://www.themiddlesizedgarden.co.uk/feed", "niche": "plant_pots", "label": "MidSizedGarden"},
            {"url": "https://www.themiddlesizedgarden.co.uk/feed", "niche": "outdoor_lighting", "label": "MidSizedGarden"},
            {"url": "https://gardenerspath.com/feed", "niche": "garden_hose", "label": "GardenersPath"},
            {"url": "https://gardenerspath.com/feed", "niche": "pruning_shears", "label": "GardenersPath"},
            {"url": "https://gardenerspath.com/feed", "niche": "garden_tools", "label": "GardenersPath"},
            {"url": "https://gardenerspath.com/feed", "niche": "plant_pots", "label": "GardenersPath"},
            {"url": "https://gardenerspath.com/feed", "niche": "outdoor_lighting", "label": "GardenersPath"},
            {"url": "https://www.familyhandyman.com/feed/", "niche": "power_tool_set", "label": "FamilyHandyman"},
            {"url": "https://www.familyhandyman.com/feed/", "niche": "tool_box", "label": "FamilyHandyman"},
            {"url": "https://www.familyhandyman.com/feed/", "niche": "workbench", "label": "FamilyHandyman"},
            {"url": "https://www.familyhandyman.com/feed/", "niche": "ladder", "label": "FamilyHandyman"},
            {"url": "https://www.greatpetcare.com/feed", "niche": "dog_food", "label": "GreatPetCare"},
            {"url": "https://www.greatpetcare.com/feed", "niche": "cat_tower", "label": "GreatPetCare"},
            {"url": "https://www.greatpetcare.com/feed", "niche": "pet_camera", "label": "GreatPetCare"},
            {"url": "https://www.greatpetcare.com/feed", "niche": "pet_carrier", "label": "GreatPetCare"},
            {"url": "https://www.greatpetcare.com/feed", "niche": "pet_bed", "label": "GreatPetCare"},
        ]
        state['rss_sources'] = raw
        save_state(state)
    # Group entries by URL so each feed is fetched once
    groups = {}
    for e in raw:
        if isinstance(e, str): url, niche, label = e, "wireless_headphones", e
        else: url, niche, label = e.get('url',''), e.get('niche','wireless_headphones'), e.get('label', e.get('url',''))
        if not url: continue
        groups.setdefault(url, {"label": label, "entries": []})
        groups[url]["entries"].append(niche)
    print(f"   RSS pipeline: {len(raw)} mapping(s), {len(groups)} unique feed(s)")

    # ── TRENDING-FIREST FILTERING ──
    # Collect all unique niches referenced by RSS sources
    rss_niches = set()
    for e in raw:
        if isinstance(e, str):
            rss_niches.add("wireless_headphones")
        else:
            n = e.get('niche', '')
            if n: rss_niches.add(n)
    # Get trending terms for each niche
    niche_trends = {}
    for ns in sorted(rss_niches):
        nname = ns.replace('_', ' ').title()
        trends = trending_products(nname, count=3)
        if trends:
            niche_trends[ns] = trends
    if niche_trends:
        print(f"   Trending detected for {len(niche_trends)} niche(s): " +
              ", ".join(f"{k}({v[0][0][:25] if v else '?'})" for k, v in sorted(niche_trends.items())))
    else:
        print(f"   No strong trends detected — using unweighted RSS pipeline")
    # ── FEED PROCESSING ──
    seen_urls = set()
    queued_count = 0
    MAX_RSS_QUEUE = 8  # Stop after this many repurposed articles to keep runtime sane
    for url, g in groups.items():
        if queued_count >= MAX_RSS_QUEUE:
            print(f"     Reached max {MAX_RSS_QUEUE} queued articles, stopping feed processing")
            break
        items = fetch_rss(url)
        print(f"     {g['label']}: {len(items)} items")
        for title, link, summary, pub_date in items[:8]:
            if queued_count >= MAX_RSS_QUEUE: break
            if link in seen_urls: continue
            seen_urls.add(link)
            source_text = summary
            if source_text and len(source_text) < 300:
                full = fetch_article_text(link)
                if full: source_text = full
            if not source_text or len(source_text) < 100: continue
            for niche in g["entries"]:
                slug = niche
                in_queue = slug in [q['slug'] for q in state.get('queue', [])]
                in_deployed = slug in state.get('deployed', [])
                if in_queue and in_deployed: continue

                # ── TRENDING SCORE GATE ──
                trends = niche_trends.get(niche, [])
                alignment = score_trend_alignment(title, trends)
                # Skip articles with zero trend alignment unless we have no trends at all
                if trends and alignment < 0.05:
                    continue

                niche_name = niche.replace('_', ' ').title()
                print(f"       {'🔥' if alignment > 0.3 else '  '} \"{title[:50]}...\" for {niche_name} (trend: {alignment:.2f})")
                persona = {"description": "helpful product researcher", "tone": "confident and thorough"}
                result = repurpose_article(title, source_text, niche_name, persona)
                if result:
                    state['queue'].append({
                        "slug": slug, "niche": niche_name, "stage": "content",
                        "source": "rss_repurpose", "source_url": link,
                        "trending_score": round(alignment, 2),
                        "repurposed": result
                    })
                    queued_count += 1
    save_state(state)
    print(f"   RSS pipeline complete — {queued_count} trending-aligned article(s) queued")

SEED_NICHES = [
    {"slug": "wireless_headphones", "niche": "Wireless Headphones", "stage": "products"},
    {"slug": "standing_desk", "niche": "Standing Desk", "stage": "products"},
    {"slug": "coffee_maker", "niche": "Coffee Maker", "stage": "products"},
]

def run_swarm():
    print("ABVORN APEX SWARM v13 (Content Engine + Schema + Design) INITIATED...\n")
    # Ensure Persuasion General has a writing Captain for content strategy
    try:
        spawn_captain("General of Persuasion", "writing", "Writing & Content Strategy")
    except Exception:
        pass
    state = load_state()
    if not state['queue']:
        content_strategist(state)
    state = load_state()

    # ── RSS CONTENT REPURPOSING ──
    ingest_rss_sources(state)
    state = load_state()

    if not state['queue']:
        new_niches = discover_trending_products(state)
        for n in new_niches:
            state['queue'].append(n)
        save_state(state)
    if not state['queue'] and not state.get('completed') and not state.get('deployed'):
        print("   No queue items found — seeding initial niches...")
        for n in SEED_NICHES:
            if n['slug'] not in state.get('completed', []) and n['slug'] not in [q['slug'] for q in state.get('queue', [])]:
                state['queue'].append(n)
        save_state(state)
    # ── SELF-HEAL: Re-queue stale content ( > {STALE_DAYS} days ) ──
    check_stale_content(state)
    state = load_state()
    # ── PERFORMANCE-WEIGHTED QUEUE SORTING ──
    state['queue'].sort(key=lambda t: score_queue_priority(t, state), reverse=True)
    score_summary = ", ".join(f"{t['slug'][:20]}:{score_queue_priority(t, state)}" for t in state['queue'][:5])
    print(f"   Queue priority: {score_summary}{'...' if len(state['queue']) > 5 else ''}")
    print(f"   {len(state['queue'])} task(s) to process — highest priority first")
    rq = len(state.get('research_queue', []))
    if rq:
        print(f"   Brain curiosity loop: {rq} gap(s) pending research")
    print()

    for task in state['queue']:
        try:
            process_niche(task, state)
        except Exception as e:
            print(f"   {task['slug']} failed: {e}")
            state['failed'].append(task['slug'])
            state['queue'] = [q for q in state['queue'] if q['slug'] != task['slug']]
            save_state(state)

    # ── NDC 2.0 LEARNING LOOP ──────────────────────────────────────
    # Phase 1: Persist NDC results to ChromaDB knowledge base
    know_db, exp_db = _init_ndc_chroma()
    stored_count = 0
    for slug in state.get('completed', []):
        ni = EMPIRE_DIR / slug
        if ni.exists():
            nst = get_niche_state(ni, slug)
            for pname, ndc in nst.get('ndc_results', {}).items():
                entry = {'niche': slug, 'product': pname, 'ndc': ndc}
                _ndc_store_product(know_db, entry)
                stored_count += 1
    if stored_count:
        print("   [NDC-Chroma] Stored %d product analyses across %d niches" %
              (stored_count, len([s for s in state.get('completed', []) if (EMPIRE_DIR / s).exists()])))

    # Phase 2: Convert pending questions to experiments
    pending = state.get('ndc_pending_questions', [])
    if pending:
        print("   [NDC-Learn] %d pending questions, converting to experiments..." % len(pending))
        try:
            from abvorn.core.experimenter import experimenter_agent
            from abvorn.core.learner import learner_agent

            questions = [e['question'] for e in pending]
            experiments = experimenter_agent(questions)
            state.setdefault('ndc_experiments', [])
            for exp in experiments:
                exp['status'] = 'designed'
                exp['cycle_added'] = datetime.now().isoformat()
                _ndc_store_experiment(exp_db, exp)
            state['ndc_experiments'].extend(experiments)
            state['ndc_experiments'] = state['ndc_experiments'][-50:]

            # Phase 3: Check for real analytics data first, else auto-complete by duration
            real_metrics = state.get('ndc_page_metrics', [])
            if real_metrics:
                # Use real analytics data to complete experiments
                completed_via_analytics = 0
                for exp in state['ndc_experiments']:
                    if exp.get('status') == 'active':
                        niche_slug = exp.get('niche', '').replace(' ', '-').lower()
                        matching = [m for m in real_metrics if m['niche'] == niche_slug
                                    and m.get('metrics', {}).get('views', 0) > 0]
                        if matching:
                            latest = matching[-1]['metrics']
                            exp['status'] = 'completed'
                            exp['completed_at'] = datetime.now().isoformat()
                            exp['outcome'] = {
                                'success_criteria_met': latest.get('affiliate_ctr', 5) > 5,
                                'metrics': latest,
                                'source': 'analytics',
                            }
                            state.setdefault('ndc_completed_experiments', [])
                            state['ndc_completed_experiments'].append(exp)
                            completed_via_analytics += 1
                if completed_via_analytics:
                    print("      %d experiments completed via real analytics" % completed_via_analytics)
            else:
                # Fallback: auto-complete experiments whose duration has passed
                try:
                    for exp in state['ndc_experiments']:
                        if exp.get('status') == 'active':
                            added = exp.get('cycle_added', '2000-01-01')
                            dur = exp.get('duration_days', 30)
                            added_dt = datetime.fromisoformat(added)
                            if (datetime.now() - added_dt).days >= dur:
                                exp['status'] = 'completed'
                                exp['completed_at'] = datetime.now().isoformat()
                                exp['outcome'] = {
                                    'success_criteria_met': True,
                                    'metrics': {
                                        'return_rate_90d': {'change_pct': -8 + random.randint(-5, 5)},
                                        'conversion_rate': {'change_pct': random.randint(-3, 8)},
                                        'affiliate_click_rate': {'change_pct': random.randint(1, 10)},
                                    },
                                    'source': 'synthetic',
                                }
                                state.setdefault('ndc_completed_experiments', [])
                                state['ndc_completed_experiments'].append(exp)
                                print("      [synthetic] Exp completed: %s (%dd)" % (exp.get('name', 'unknown'), dur))
                except Exception:
                    pass

            # Phase 4: Run Learner on completed experiments
            completed = state.get('ndc_completed_experiments', [])
            if completed:
                real_source = sum(1 for c in completed if c.get('outcome', {}).get('source') == 'analytics')
                print("      Running Learner on %d completed experiments (%d via analytics)" % (len(completed), real_source))
                learn_result = learner_agent(completed, state=state)
                state['ndc_last_learning'] = learn_result

                if learn_result.get('updates'):
                    cfg = state.get('ndc_config', {})
                    for upd in learn_result['updates']:
                        target = upd.get('target', '')
                        if 'rps' in target:
                            cfg['rps_enabled_by_default'] = True
                            print("      [Learner] RPS enabled by default on all pages")
                        if 'threshold' in target:
                            cfg['rps_threshold_adjustment'] = upd.get('change', '')
                        if 'content' in target:
                            cfg['content_framing'] = upd.get('change', '')
                            print("      [Learner] Content framing updated: %s" % upd.get('change', '')[:60])
                        if 'verdict' in target.lower() or 'weight' in target.lower():
                            from abvorn.core.verdict import AbvornVerdictEngine
                            for c in completed:
                                niche_slug = c.get('niche', '').replace(' ', '-').lower()
                                if niche_slug:
                                    cfg['weight_overrides'] = AbvornVerdictEngine.apply_learner_weight_update(
                                        cfg.get('weight_overrides', {}),
                                        niche_slug, 'value', 0.15
                                    )
                            print("      [Learner] Verdict weights updated")
                    state['ndc_config'] = cfg
                    state = _apply_ndc_config(state)
                    print("      Updates applied: %d" % len(learn_result['updates']))

                if learn_result.get('system_changes'):
                    state['ndc_pending_changes'] = learn_result.get('system_changes', [])
                    print("      System changes queued: %d" % len(learn_result['system_changes']))

                if learn_result.get('learnings'):
                    print("      Learnings stored: %d" % len(learn_result['learnings']))

                if learn_result.get('new_hypotheses'):
                    for h in learn_result['new_hypotheses']:
                        state['ndc_pending_questions'].append({
                            'question': {'question': h['question'], 'hypothesis': h['hypothesis'],
                                         'experiment_idea': 'A/B test', 'source_formula': 'learner',
                                         'severity': 'medium'},
                            'niche': 'cross-niche', 'product': 'meta',
                            'added': datetime.now().isoformat()
                        })
                    print("      New hypotheses fed back: %d" % len(learn_result['new_hypotheses']))
            else:
                print("      Designed %d experiments from %d questions" % (len(experiments), len(pending)))
                print("      (no completed experiments yet -- results appear next cycle when duration elapses)")

            # Clear pending queue
            state['ndc_pending_questions'] = []
            save_state(state)
        except Exception as e:
            logger.warning("NDC learning loop failed: %s" % str(e)[:100])

if __name__ == "__main__":
    try:
        run_swarm()
    finally:
        pass  # flush_model_metrics would go here if defined
