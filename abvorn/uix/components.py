"""UIXComponents — generates interactive HTML/JS for blog posts."""

import html
import json
from datetime import datetime
from urllib.parse import quote

UX_NOTES = {
    "social_proof": [
        "serial_position: Most impressive stat (largest number) placed first",
        "common_region: All stats grouped in single card container",
    ],
    "reactions_bar": [
        "fitts_law: Large touch targets, thumb-friendly sizing",
        "feedback: Hover/active CSS states for every action",
        "consistency: All action buttons share same visual language",
    ],
    "_share_buttons": [
        "hick_law: Only top 4 platforms shown (X, LinkedIn, FB, Email), copy-link moved to secondary",
        "serial_position: Most-used platforms placed first in natural reading order",
    ],
    "comment_section": [
        "progressive_disclosure: Comment form hidden behind 'Join the conversation' button, expands on click",
        "cognitive_load: Clear labels, inline validation hints, char counter, named inputs",
    ],
    "full_engagement_block": [
        "wraps all enhanced components into a single annotated block",
    ],
}

class UIXComponents:
    """Generates interactive social components embedded into blog HTML."""

    @staticmethod
    def get_ux_annotation(component: str) -> str:
        """Return HTML comment with UX principle justifications for a component."""
        notes = UX_NOTES.get(component, [])
        if not notes:
            return ""
        lines = "".join(f"    <!-- ux: {note} -->\n" for note in notes)
        return f"<!-- ux-annotation: {component} -->\n{lines}<!-- /ux-annotation -->\n"

    @staticmethod
    def social_proof(likes: int = 0, shares: int = 0, comments: int = 0, readers: int = 0) -> str:
        """Social proof bar — 'X people loved this', 'Y shared'.

        UX: serial_position (largest number first), common_region (single card).
        """
        items = []
        if readers:
            items.append((readers, 'readers', f'<span class="uix-proof-item"><span class="dot green"></span><strong>{readers}</strong> reading now</span>'))
        if likes:
            items.append((likes, 'likes', f'<span class="uix-proof-item"><span class="dot pink"></span><strong>{likes}</strong> people liked this</span>'))
        if shares:
            items.append((shares, 'shares', f'<span class="uix-proof-item"><span class="dot blue"></span><strong>{shares}</strong> shares</span>'))
        if comments:
            items.append((comments, 'comments', f'<span class="uix-proof-item"><span class="dot"></span><strong>{comments}</strong> comments</span>'))
        items.sort(key=lambda x: x[0], reverse=True)
        parts = [item[2] for item in items]
        if not parts:
            parts.append('<span class="uix-proof-item">Be the first to react</span>')
        annotation = UIXComponents.get_ux_annotation("social_proof")
        return f'{annotation}<div class="uix-social-proof">{"".join(parts)}</div>'

    @staticmethod
    def reactions_bar(post_id: int, liked: bool = False, loved: bool = False,
                      like_count: int = 0, love_count: int = 0) -> str:
        """Like + Love reaction buttons with counters.

        UX: fitts_law (larger thumb-friendly buttons), feedback (hover/active), consistency.
        """
        like_cls = "uix-btn active" if liked else "uix-btn"
        love_cls = "uix-btn loved" if loved else "uix-btn"
        annotation = UIXComponents.get_ux_annotation("reactions_bar")
        return f"""{annotation}<div class="uix-reactions" data-post-id="{post_id}">
  <button class="{like_cls} uix-reaction-btn" data-action="like" data-post-id="{post_id}" onclick="uixReact(this)">
    <span class="icon">{'👍' if liked else '👍'}</span>
    <span class="count">{like_count}</span>
    <span class="label">Like</span>
  </button>
  <button class="{love_cls} uix-reaction-btn" data-action="love" data-post-id="{post_id}" onclick="uixReact(this)">
    <span class="icon">{'❤️' if loved else '❤️'}</span>
    <span class="count">{love_count}</span>
    <span class="label">Love</span>
  </button>
  {UIXComponents._share_buttons(post_id, like_count + love_count)}
</div>"""

    @staticmethod
    def _share_buttons(post_id: int, engagement: int = 0) -> str:
        """Share button cluster — top 4 platforms visible, copy-link secondary.

        UX: hick_law (limit visible choices to 4), serial_position (most-used first).
        """
        url = f"https://abvorn.com/p/{post_id}"
        encoded = quote(url)
        title = quote("Check this out!")
        annotation = UIXComponents.get_ux_annotation("_share_buttons")
        return f"""{annotation}<div class="uix-share">
  <span class="uix-share-label">Share</span>
  <a class="uix-share-btn share-x" href="https://twitter.com/intent/tweet?url={encoded}&text={title}" target="_blank" rel="noopener" title="Share on X" data-platform="x" onclick="uixTrackShare({post_id},'x')">𝕏</a>
  <a class="uix-share-btn share-linkedin" href="https://linkedin.com/sharing/share-offsite/?url={encoded}" target="_blank" rel="noopener" title="Share on LinkedIn" data-platform="linkedin" onclick="uixTrackShare({post_id},'linkedin')">in</a>
  <a class="uix-share-btn share-facebook" href="https://facebook.com/sharer/sharer.php?u={encoded}" target="_blank" rel="noopener" title="Share on Facebook" data-platform="facebook" onclick="uixTrackShare({post_id},'facebook')">f</a>
  <a class="uix-share-btn share-email" href="mailto:?subject={title}&body={encoded}" title="Share via Email" data-platform="email" onclick="uixTrackShare({post_id},'email')">✉</a>
  <details class="uix-share-more">
    <summary class="uix-share-more-toggle" title="More share options">⋯</summary>
    <button class="uix-share-btn share-copy" title="Copy link" onclick="uixCopyLink({post_id}, this)" data-platform="copy">🔗 Copy link</button>
  </details>
  {f'<span class="uix-share-count">{engagement} reactions</span>' if engagement else ''}
</div>"""

    @staticmethod
    def comment_section(post_id: int, comments: list = None) -> str:
        """Full comment section — collapsed form + display.

        UX: progressive_disclosure (form behind toggle), cognitive_load (clear labels, validation hints).
        """
        comments = comments or []
        comment_html = ""
        if comments:
            for c in comments:
                author = html.escape(c.get("author", "Reader"), quote=True)
                body = html.escape(c.get("body", ""), quote=True)
                created = c.get("created_at", "")
                try:
                    d = datetime.fromisoformat(created)
                    time_str = d.strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    time_str = ""
                comment_html += f"""<div class="uix-comment">
  <div class="author">{author} <span class="time">{time_str}</span></div>
  <div class="body">{body}</div>
</div>"""
        else:
            comment_html = '<div class="uix-no-comments">No comments yet. Start the conversation!</div>'

        annotation = UIXComponents.get_ux_annotation("comment_section")
        return f"""{annotation}<div class="uix-comments" data-post-id="{post_id}">
  <h3>Comments <span class="count">({len(comments)})</span></h3>
  <button class="uix-comment-toggle" onclick="this.nextElementSibling.classList.toggle('open');this.classList.toggle('hidden')">Join the conversation</button>
  <form class="uix-comment-form collapsed" onsubmit="uixSubmitComment(event, {post_id})">
    <label for="comment-author-{post_id}">Your name</label>
    <input type="text" id="comment-author-{post_id}" name="author" placeholder="e.g. Alex" required maxlength="50" pattern="[A-Za-z0-9 ]{{2,50}}" title="2-50 characters, letters and numbers only">
    <span class="uix-hint">Public — displayed with your comment</span>
    <label for="comment-body-{post_id}">Comment</label>
    <textarea id="comment-body-{post_id}" name="body" placeholder="Share your thoughts..." required maxlength="1000"></textarea>
    <span class="uix-hint uix-char-hint" id="char-hint-{post_id}">0 / 1000</span>
    <button type="submit">Post Comment</button>
  </form>
  <div id="uix-comment-list">{comment_html}</div>
</div>"""

    @staticmethod
    def full_engagement_block(post_id: int, engagement: dict = None) -> str:
        """Complete engagement block — social proof + reactions + comments.

        UX: wraps annotated components into the full post footer.
        """
        e = engagement or {}
        likes = e.get("likes", {})
        shares = e.get("shares", {})
        comments_data = e.get("comments", {})
        annotation = UIXComponents.get_ux_annotation("full_engagement_block")
        return (
            annotation +
            UIXComponents.social_proof(
                likes=likes.get("total", 0),
                shares=shares.get("total", 0),
                comments=comments_data.get("count", 0),
                readers=0
            ) +
            UIXComponents.reactions_bar(
                post_id,
                liked=False, loved=False,
                like_count=likes.get("like", 0),
                love_count=likes.get("love", 0)
            ) +
            UIXComponents.comment_section(post_id, comments_data.get("recent", []))
        )


UIX_SCRIPT_JS = """<script>
// ===== Abvorn UIX — Interactive Layer =====
(function(){'use strict';

function uixToast(msg){var t=document.getElementById('uix-toast');if(!t){t=document.createElement('div');t.id='uix-toast';t.className='uix-toast';document.body.appendChild(t)}t.textContent=msg;t.classList.add('show');setTimeout(function(){t.classList.remove('show')},2500)}

function uixEscape(s){var d=document.createElement('div');d.appendChild(document.createTextNode(s));return d.innerHTML}

window.uixReact=function(btn){var action=btn.getAttribute('data-action');var pid=btn.getAttribute('data-post-id');var count=btn.querySelector('.count');
var x=new XMLHttpRequest();x.open('POST','/api/react',true);x.setRequestHeader('Content-Type','application/json');
x.onload=function(){if(x.status===200||x.status===201){var d=JSON.parse(x.responseText);count.textContent=d[action];
if(action==='like'){btn.classList.toggle('active');uixToast('👍 Thanks for the like!')}
if(action==='love'){btn.classList.toggle('loved');uixToast('❤️ Spread the love!')}}else{uixToast('Could not register reaction')}};
x.onerror=function(){uixToast('Connection error')};
x.send(JSON.stringify({post_id:parseInt(pid),action:action}))};

window.uixTrackShare=function(pid,platform){
var x=new XMLHttpRequest();x.open('POST','/api/share',true);x.setRequestHeader('Content-Type','application/json');
x.send(JSON.stringify({post_id:pid,platform:platform}))};

window.uixCopyLink=function(pid,btn){
var url=window.location.href;if(navigator.clipboard){navigator.clipboard.writeText(url).then(function(){
btn.classList.add('copied');btn.textContent='✓';uixToast('Link copied!');setTimeout(function(){btn.classList.remove('copied');btn.innerHTML='🔗'},2000)})}else{
var ta=document.createElement('textarea');ta.value=url;document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);btn.classList.add('copied');btn.textContent='✓';uixToast('Link copied!');setTimeout(function(){btn.classList.remove('copied');btn.innerHTML='🔗'},2000)}
uixTrackShare(pid,'copy')};

window.uixSubmitComment=function(e,pid){e.preventDefault();var author=document.getElementById('comment-author-'+pid).value.trim();var body=document.getElementById('comment-body-'+pid).value.trim();if(!author||!body)return;
var btn=e.target.querySelector('button');btn.disabled=true;btn.textContent='Posting...';
var x=new XMLHttpRequest();x.open('POST','/api/comment',true);x.setRequestHeader('Content-Type','application/json');
x.onload=function(){if(x.status===200||x.status===201){
var d=JSON.parse(x.responseText);if(d.status==='pending'){uixToast('Comment submitted for review!')}else{uixToast('Comment posted!')}
document.getElementById('comment-body-'+pid).value='';var list=document.getElementById('uix-comment-list');
var newC=document.createElement('div');newC.className='uix-comment'+(d.status==='pending'?' pending':'');
newC.innerHTML='<div class=\"author\">'+uixEscape(author)+' <span class=\"time\">Just now</span>'+(d.status==='pending'?'<span class=\"pending-badge\">Pending</span>':'')+'</div><div class=\"body\">'+uixEscape(body)+'</div>';
list.insertBefore(newC,list.firstChild)}else{uixToast('Could not post comment')};btn.disabled=false;btn.textContent='Post Comment'};
x.onerror=function(){uixToast('Connection error');btn.disabled=false;btn.textContent='Post Comment'};
x.send(JSON.stringify({post_id:pid,author:author,body:body}))};
})();
</script>"""

UIX_SCRIPT_JS = UIX_SCRIPT_JS.replace("\\", "\\\\").replace("`", "\\`")