document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.av-price-chart').forEach(function(container) {
        const dataEl = container.querySelector('.av-price-chart-data');
        if (!dataEl) return;
        let history = [];
        try {
            history = JSON.parse(dataEl.textContent || '[]');
        } catch (e) {
            return;
        }
        if (!history || history.length < 2) return;

        const canvas = container.querySelector('canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width || 200;
        const height = canvas.height || 60;
        const padding = 4;

        const prices = history.map(function(p) { return p.price; });
        const minPrice = Math.min.apply(null, prices);
        const maxPrice = Math.max.apply(null, prices);
        const range = maxPrice - minPrice || 1;

        ctx.clearRect(0, 0, width, height);

        const points = prices.map(function(price, i) {
            var x = padding + (i / (prices.length - 1)) * (width - padding * 2);
            var y = height - padding - ((price - minPrice) / range) * (height - padding * 2);
            return { x: x, y: y };
        });

        ctx.beginPath();
        ctx.strokeStyle = '#c98a2c';
        ctx.lineWidth = 2;
        points.forEach(function(pt, i) {
            if (i === 0) ctx.moveTo(pt.x, pt.y);
            else ctx.lineTo(pt.x, pt.y);
        });
        ctx.stroke();

        var last = points[points.length - 1];
        ctx.beginPath();
        ctx.fillStyle = '#c98a2c';
        ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
        ctx.fill();
    });
});

function setPriceAlert(asin, currentPrice) {
    var email = prompt('Enter your email for price drop alerts:');
    if (!email) return;
    fetch('/api/price-alerts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, asin: asin, target_price: currentPrice, current_price: currentPrice })
    }).then(function(r) { return r.json(); }).then(function(data) {
        alert(data.message || 'Alert saved');
    }).catch(function() {
        alert('Could not save alert right now.');
    });
}
