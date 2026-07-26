"""PersuasionWidget — generates embeddable HTML+JS product recommendation widget."""

import json
from html import escape


class PersuasionWidget:
    """Generates self-contained HTML+JS widget for product recommendations."""

    def render(self, context, recommendations: list, brand=None) -> str:
        if not recommendations:
            return ""

        data = {
            "niche": context.niche,
            "persona": context.persona_name,
            "stage": context.buying_stage.value,
            "products": [
                {
                    "name": r.name,
                    "tagline": r.tagline,
                    "price": r.price_range,
                    "url": r.affiliate_url,
                    "reason": r.reason_to_buy,
                    "image": r.image_url,
                }
                for r in recommendations
            ],
        }
        json_data = escape(json.dumps(data), quote=False)

        cards = ""
        for i, r in enumerate(recommendations):
            price_html = f'<span class="pr-price">{escape(r.price_range)}</span>' if r.price_range else ""
            reason_html = f'<p class="pr-reason">{escape(r.reason_to_buy)}</p>' if r.reason_to_buy else ""
            cards += f"""
<div class="pr-card" data-index="{i}">
  <a href="{escape(r.affiliate_url)}" target="_blank" rel="sponsored noopener" data-persuasion-click="{i}">
    <strong>{escape(r.name)}</strong>
    {price_html}
  </a>
  <p class="pr-tagline">{escape(r.tagline)}</p>
  {reason_html}
</div>"""

        return f"""<div id="abvorn-persuasion" class="abvorn-persuasion">
<style>
.abvorn-persuasion{{margin:24px 0;padding:16px;border:1px solid #e0e0e0;border-radius:8px;background:#fafafa;font-family:-apple-system,sans-serif;}}
.abvorn-persuasion h3{{margin:0 0 12px;font-size:16px;color:#333;}}
.pr-card{{padding:8px 0;border-bottom:1px solid #eee;}}
.pr-card:last-child{{border-bottom:none;}}
.pr-card a{{text-decoration:none;color:#1a73e8;font-size:15px;display:block;}}
.pr-card a:hover{{text-decoration:underline;}}
.pr-price{{font-size:13px;color:#666;margin-left:4px;}}
.pr-tagline{{margin:2px 0 0;font-size:13px;color:#555;}}
.pr-reason{{margin:2px 0 0;font-size:12px;color:#888;font-style:italic;}}
</style>
<h3>Recommended for you</h3>
<div class="pr-cards">{cards}</div>
<script>
(function(){{
  var w=window;
  if(w.__ABVORN_PERSUASION_INITED)return;
  w.__ABVORN_PERSUASION_INITED=true;
  var data={json_data};
  var clicks=document.querySelectorAll('[data-persuasion-click]');
  for(var i=0;i<clicks.length;i++){{
    clicks[i].addEventListener('click',function(e){{
      var idx=this.getAttribute('data-persuasion-click');
      if(navigator.sendBeacon){{
        navigator.sendBeacon('/api/persuasion/click','idx='+idx+'&niche='+data.niche+'&stage='+data.stage);
      }}
    }});
  }}
}})();
</script>
</div>"""
