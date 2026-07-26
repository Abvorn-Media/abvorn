"""Interactive UIX styling — micro-animations, reactions, social proof, dark-mode-friendly."""

UIX_STYLE_CSS = """
/* ===== Abvorn UIX — Interactive Layer ===== */

/* Reactions Bar */
.uix-reactions{display:flex;align-items:center;gap:clamp(8px,2vw,16px);flex-wrap:wrap;padding:clamp(12px,2.5vw,16px) 0;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;margin:clamp(16px,3vw,24px) 0}
.uix-btn{display:inline-flex;align-items:center;gap:6px;padding:clamp(6px,1.5vw,10px) clamp(10px,2vw,16px);border:1px solid #e0e0e0;border-radius:24px;background:#fff;cursor:pointer;font-family:'Inter',sans-serif;font-size:clamp(0.75rem,2vw,0.85rem);color:#444;transition:all 0.2s cubic-bezier(0.34,1.56,0.64,1);user-select:none;-webkit-tap-highlight-color:transparent}
.uix-btn:hover{border-color:#0066cc;color:#0066cc;transform:scale(1.05);box-shadow:0 2px 8px rgba(0,102,204,0.1)}
.uix-btn:active{transform:scale(0.95)}
.uix-btn.active{background:#f0f7ff;border-color:#0066cc;color:#0066cc}
.uix-btn.loved{background:#fff0f5;border-color:#e91e63;color:#e91e63}
.uix-btn.loved:hover{border-color:#e91e63;color:#e91e63}
.uix-btn .icon{font-size:clamp(1rem,2.5vw,1.15rem);line-height:1;transition:transform 0.2s ease}
.uix-btn.active .icon,.uix-btn.loved .icon{animation:pop 0.3s ease}
@keyframes pop{0%{transform:scale(1)}50%{transform:scale(1.3)}100%{transform:scale(1)}}
.uix-btn .count{font-variant-numeric:tabular-nums;min-width:12px}

/* Share Buttons */
.uix-share{display:flex;align-items:center;gap:clamp(6px,1.5vw,10px);flex-wrap:wrap}
.uix-share-label{font-family:'Inter',sans-serif;font-size:clamp(0.7rem,1.8vw,0.75rem);color:#999;text-transform:uppercase;letter-spacing:0.05em;font-weight:600;margin-right:4px}
.uix-share-btn{display:inline-flex;align-items:center;justify-content:center;width:clamp(32px,7vw,36px);height:clamp(32px,7vw,36px);border-radius:50%;border:1px solid #e0e0e0;background:#fff;cursor:pointer;font-size:clamp(0.9rem,2.2vw,1rem);transition:all 0.2s ease;text-decoration:none;color:#555}
.uix-share-btn:hover{transform:translateY(-2px);box-shadow:0 3px 10px rgba(0,0,0,0.1)}
.uix-share-btn.share-x:hover{background:#000;color:#fff;border-color:#000}
.uix-share-btn.share-linkedin:hover{background:#0077b5;color:#fff;border-color:#0077b5}
.uix-share-btn.share-facebook:hover{background:#1877f2;color:#fff;border-color:#1877f2}
.uix-share-btn.share-email:hover{background:#666;color:#fff;border-color:#666}
.uix-share-btn.share-copy:hover{background:#1a1a1a;color:#fff;border-color:#1a1a1a}
.uix-share-btn.share-copy.copied{background:#00a86b;color:#fff;border-color:#00a86b}
.uix-share-count{font-family:'Inter',sans-serif;font-size:clamp(0.7rem,1.8vw,0.8rem);color:#888;margin-left:4px}

/* Social Proof Bar */
.uix-social-proof{display:flex;align-items:center;gap:clamp(12px,3vw,20px);padding:clamp(8px,2vw,12px) 0;margin-bottom:clamp(8px,1.5vw,12px);flex-wrap:wrap}
.uix-proof-item{display:flex;align-items:center;gap:4px;font-family:'Inter',sans-serif;font-size:clamp(0.7rem,1.8vw,0.8rem);color:#888}
.uix-proof-item .dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:4px}
.uix-proof-item .dot.green{background:#00a86b}
.uix-proof-item .dot.blue{background:#0066cc}
.uix-proof-item .dot.pink{background:#e91e63}
.uix-proof-item strong{color:#555;font-weight:600}

/* Comment Section */
.uix-comments{margin-top:clamp(24px,5vw,40px)}
.uix-comments h3{font-size:clamp(1rem,2.8vw,1.2rem);font-weight:700;font-family:'Inter',sans-serif;margin-bottom:clamp(12px,2.5vw,16px);display:flex;align-items:center;gap:8px}
.uix-comments h3 .count{font-size:clamp(0.75rem,2vw,0.85rem);color:#999;font-weight:400}
.uix-comment-form{display:flex;flex-direction:column;gap:clamp(8px,2vw,12px);margin-bottom:clamp(16px,3vw,24px);padding:clamp(12px,2.5vw,16px);background:#fafaf8;border-radius:8px;border:1px solid #eee}
.uix-comment-form label{font-family:'Inter',sans-serif;font-size:clamp(0.75rem,2vw,0.8rem);font-weight:600;color:#444}
.uix-comment-form input,.uix-comment-form textarea{font-family:'Inter',sans-serif;font-size:clamp(0.85rem,2.2vw,0.9rem);padding:clamp(8px,2vw,10px) clamp(10px,2.5vw,12px);border:1px solid #ddd;border-radius:6px;transition:border-color 0.2s;background:#fff}
.uix-comment-form input:focus,.uix-comment-form textarea:focus{outline:none;border-color:#0066cc;box-shadow:0 0 0 3px rgba(0,102,204,0.1)}
.uix-comment-form textarea{min-height:80px;resize:vertical}
.uix-comment-form button{align-self:flex-start;padding:clamp(8px,2vw,10px) clamp(16px,4vw,24px);background:#1a1a1a;color:#fff;border:none;border-radius:6px;font-family:'Inter',sans-serif;font-size:clamp(0.8rem,2vw,0.85rem);font-weight:600;cursor:pointer;transition:background 0.2s}
.uix-comment-form button:hover{background:#333}
.uix-comment-form button:disabled{opacity:0.5;cursor:not-allowed}
.uix-comment{margin-bottom:clamp(12px,2.5vw,16px);padding:clamp(10px,2vw,14px);background:#fff;border:1px solid #eee;border-radius:8px;transition:opacity 0.3s}
.uix-comment .author{font-family:'Inter',sans-serif;font-weight:600;font-size:clamp(0.8rem,2vw,0.85rem);color:#1a1a1a;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.uix-comment .time{font-size:clamp(0.65rem,1.5vw,0.7rem);color:#aaa;font-weight:400}
.uix-comment .body{font-size:clamp(0.85rem,2.2vw,0.92rem);color:#333;line-height:1.5}
.uix-comment.pending{opacity:0.6}
.uix-comment .pending-badge{font-size:clamp(0.6rem,1.5vw,0.65rem);color:#f5a623;font-weight:500;background:#fff8e0;padding:2px 6px;border-radius:3px}
.uix-no-comments{text-align:center;padding:clamp(20px,4vw,32px);color:#aaa;font-family:'Inter',sans-serif;font-size:clamp(0.85rem,2.2vw,0.9rem)}

/* Toast Notification */
.uix-toast{position:fixed;bottom:clamp(16px,4vw,24px);left:50%;transform:translateX(-50%) translateY(100px);background:#1a1a1a;color:#fff;padding:clamp(10px,2.5vw,14px) clamp(16px,4vw,24px);border-radius:8px;font-family:'Inter',sans-serif;font-size:clamp(0.8rem,2vw,0.85rem);z-index:1000;opacity:0;transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1);box-shadow:0 4px 20px rgba(0,0,0,0.2);pointer-events:none;white-space:nowrap;max-width:90vw}
.uix-toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* Engagement Stats Bar (above article header) */
.uix-stats-bar{display:flex;gap:clamp(16px,4vw,24px);padding:clamp(6px,1.5vw,8px) 0;margin-bottom:clamp(8px,1.5vw,12px);flex-wrap:wrap}
.uix-stat{display:flex;align-items:center;gap:4px;font-family:'Inter',sans-serif;font-size:clamp(0.7rem,1.8vw,0.78rem);color:#999}
.uix-stat strong{color:#666;font-weight:600}

/* Mobile adjustments */
@media(max-width:600px){.uix-reactions{flex-direction:column;align-items:stretch;gap:8px}.uix-share{justify-content:center}.uix-btn{justify-content:center}.uix-comment-form button{width:100%;text-align:center}}
@media print{.uix-reactions,.uix-share,.uix-social-proof,.uix-comments,.uix-toast{display:none!important}}
"""