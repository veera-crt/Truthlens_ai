console.log("[TruthLens AI] Injected Forensic Overlay");

function injectOverlay(data) {
    const videoOwner = document.querySelector("#owner-container");
    if (!videoOwner) return;

    if (document.getElementById("truthlens-badge")) return;

    const badge = document.createElement("div");
    badge.id = "truthlens-badge";
    badge.style = `
        background: rgba(10, 10, 10, 0.9);
        border: 1px solid ${data.trust_index > 70 ? '#00ff88' : '#ff4444'};
        padding: 10px;
        margin-top: 10px;
        border-radius: 8px;
        color: white;
        font-family: monospace;
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    `;
    
    badge.innerHTML = `
        <div style="font-weight:bold; color:var(--accent); margin-bottom:4px;">TRUTHLENS AI VERDICT</div>
        <div style="display:flex; justify-content:space-between;">
            <span>Trust Index:</span>
            <span style="color:${data.trust_index > 70 ? '#00ff88' : '#ff4444'}">${data.trust_index}%</span>
        </div>
        <div style="font-size:0.7rem; color:#aaa; margin-top:4px;">${data.nlp.is_suspicious ? '⚠ Suspicious manipulation cues detected.' : '✓ No major manipulation cues found.'}</div>
    `;
    
    videoOwner.appendChild(badge);
}

// Polling for video ID change
let lastId = "";
setInterval(async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('v');
    
    if (videoId && videoId !== lastId) {
        lastId = videoId;
        console.log("[TruthLens AI] Analyzing video:", videoId);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/video/${videoId}`);
            const data = await response.json();
            injectOverlay(data);
        } catch (e) {
            console.error("[TruthLens AI] Connection to backend failed.");
        }
    }
}, 3000);
