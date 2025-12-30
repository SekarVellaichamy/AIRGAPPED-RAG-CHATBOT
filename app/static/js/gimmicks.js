/**
 * IAF Futuristic Theme Gimmicks
 * - Particle Background
 * - Text Decoding Effect
 */

document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initFuturisticText();
});

/* =========================================
   Particle Network Background
   ========================================= */
function initParticles() {
    // Create canvas if it doesn't exist
    let canvas = document.getElementById('particles-canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'particles-canvas';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.zIndex = '-1';
        canvas.style.pointerEvents = 'none'; // Click-through
        document.body.prepend(canvas);
    }

    const ctx = canvas.getContext('2d');
    let width, height;
    let particles = [];

    // Configuration
    const particleCount = 60; // Reduced count for subtlety
    const connectionDistance = 150;
    const speed = 0.3;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    class Particle {
        constructor() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.vx = (Math.random() - 0.5) * speed;
            this.vy = (Math.random() - 0.5) * speed;
            this.size = Math.random() * 2 + 1;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            // Bounce off edges
            if (this.x < 0 || this.x > width) this.vx *= -1;
            if (this.y < 0 || this.y > height) this.vy *= -1;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0, 176, 255, 0.3)'; // IAF Sky Blue
            ctx.fill();
        }
    }

    function init() {
        resize();
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);

        particles.forEach((p, index) => {
            p.update();
            p.draw();

            // Draw connections
            for (let j = index + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectionDistance) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(0, 176, 255, ${0.1 * (1 - dist / connectionDistance)})`;
                    ctx.lineWidth = 1;
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        });

        requestAnimationFrame(animate);
    }

    window.addEventListener('resize', resize);
    init();
    animate();
}

/* =========================================
   Futuristic Text Decoding Effect
   ========================================= */
function initFuturisticText() {
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    const targets = document.querySelectorAll('.navbar-brand');

    targets.forEach(target => {
        let iterations = 0;
        const interval = setInterval(() => {
            target.innerText = target.innerText
                .split("")
                .map((letter, index) => {
                    if (index < iterations) {
                        return target.dataset.value?.[index] || letter; // Preserves original text if stored
                    }
                    return letters[Math.floor(Math.random() * 26)];
                })
                .join("");

            if (iterations >= target.dataset.value?.length || iterations > 20) {
                clearInterval(interval);
                target.innerText = target.dataset.value || "IAF SECURE CHAT"; // Fallback
            }

            iterations += 1 / 3;
        }, 30);

        // Store original text for stable recovery
        if (!target.dataset.value) target.dataset.value = target.innerText;
    });
}
