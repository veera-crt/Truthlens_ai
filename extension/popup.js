document.addEventListener('DOMContentLoaded', async () => {
  const initState = document.getElementById('init-state');
  const loadingState = document.getElementById('loading-state');
  const resultState = document.getElementById('result-state');
  const analyzeBtn = document.getElementById('analyze-btn');
  const videoInfo = document.getElementById('video-info');
  const videoTitle = document.getElementById('video-title');
  const statusBadge = document.getElementById('status-badge');

  // 1. Get the current active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (tab.url && tab.url.includes("youtube.com/watch")) {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "ANALYZE VIDEO";
    videoInfo.style.display = 'block';
    videoTitle.textContent = tab.title.replace(" - YouTube", "");
    
    // Auto-analyze
    analyzeBtn.addEventListener('click', () => runAnalysis(tab.url, tab.title));
  } else {
    analyzeBtn.textContent = "Not a YouTube Video";
  }

  async function runAnalysis(url, title) {
    initState.classList.remove('active');
    loadingState.classList.add('active');
    statusBadge.textContent = "ANALYZING";
    statusBadge.style.color = "var(--warn)";
    statusBadge.style.borderColor = "var(--warn)";

    try {
      const response = await fetch("http://127.0.0.1:5001/api/extension/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, title: title })
      });

      if (response.status === 429 || response.status === 202) {
        loadingState.innerHTML = `<div class="loader" style="border-top-color:var(--warn)"></div>
          <p style="color:var(--warn); text-align:center; margin-top:15px; font-size:0.85rem;">
          Analysis is running in the background...<br><br>
          <span style="color:var(--text-dim);font-size:0.75rem;">Depending on video length and complexity, deep forensic analysis can take anywhere from a few minutes up to 30 minutes.<br><br>You can safely close this popup and check back later!</span></p>`;
        statusBadge.textContent = "PROCESSING";
        statusBadge.style.color = "var(--warn)";
        return;
      }
      
      if (!response.ok) {
        throw new Error("Failed to connect to TruthLens backend.");
      }

      const data = await response.json();
      
      // Update UI
      loadingState.classList.remove('active');
      resultState.classList.add('active');
      statusBadge.textContent = "COMPLETED";
      statusBadge.style.color = "var(--safe)";
      statusBadge.style.borderColor = "var(--safe)";

      populateResults(data);

    } catch (err) {
      loadingState.innerHTML = `<p style="color:var(--danger); text-align:center;">Error: Backend Offline.<br><br><span style="font-size:0.75rem;color:var(--text-dim);">Is python3 app.py running on port 5001?</span></p>`;
      statusBadge.textContent = "OFFLINE";
      statusBadge.style.color = "var(--danger)";
      statusBadge.style.borderColor = "var(--danger)";
    }
  }

  function populateResults(data) {
    const ti = data.trust_index || 0;
    const ms = data.manipulation_risk || 0;
    const vs = data.virality_score || 0;

    document.getElementById('val-trust').textContent = `${ti.toFixed(1)}%`;
    document.getElementById('val-manip').textContent = `${(ms * 100).toFixed(1)}%`;
    document.getElementById('val-viral').textContent = `${(vs * 100).toFixed(1)}%`;

    // Colors
    document.getElementById('card-trust').style.borderLeftColor = ti > 70 ? 'var(--safe)' : (ti > 40 ? 'var(--warn)' : 'var(--danger)');
    document.getElementById('val-trust').style.color = ti > 70 ? 'var(--safe)' : (ti > 40 ? 'var(--warn)' : 'var(--danger)');
    
    document.getElementById('card-manip').style.borderLeftColor = ms > 0.5 ? 'var(--danger)' : (ms > 0.25 ? 'var(--warn)' : 'var(--safe)');
    document.getElementById('val-manip').style.color = ms > 0.5 ? 'var(--danger)' : (ms > 0.25 ? 'var(--warn)' : 'var(--safe)');
    
    document.getElementById('card-viral').style.borderLeftColor = vs > 0.5 ? 'var(--accent)' : 'var(--muted)';
    
    // --- 5-Category Verdict & Dynamic Conclusion ---
    const vs_pct = vs * 100;
    const ms_pct = ms * 100;
    
    let category = "AUTHENTIC";
    let verdictTitle = "Highly Trustworthy & Safe";
    let verdictColor = "var(--safe)";
    let explanation = "The content exhibits high integrity. No language manipulation or propaganda markers were detected, and key assertions align with verified evidence. It can be widely trusted as a reliable source of information.";

    if (ti < 20) {
        category = "CRITICAL";
        verdictTitle = "Severe Manipulation / Falsehood";
        verdictColor = "#ff3366"; // Vivid magenta/red
        explanation = "Severe levels of urgency, fear propagation, or propaganda signals identified. Factual assertions are strongly contradicted by verified external sources. The content represents an extreme risk of active misinformation.";
    } else if (ti < 40 || ms_pct > 60) {
        category = "HIGH RISK";
        verdictTitle = "Questionable Content";
        verdictColor = "var(--danger)";
        explanation = "Significant signs of language manipulation, fear-inducing rhetoric, or unverified claims were found. There is a high probability of bias, manipulation, or misleading framing.";
    } else if (ti < 60 || ms_pct > 35) {
        category = "MODERATE";
        verdictTitle = "Caution Advised";
        verdictColor = "var(--warn)";
        explanation = "This content exhibits some urgency spikes or propaganda cues. Factual claims are partially unverified or subjective. We recommend caution and cross-referencing before sharing.";
    } else if (ti < 80 || ms_pct > 15) {
        category = "LOW RISK";
        verdictTitle = "Mostly Reliable";
        verdictColor = "var(--accent)";
        explanation = "Minimal rhetorical inflation or urgency triggers detected. The main assertions are factual with robust evidence backing. Use basic discretion.";
    }
    
    // Dynamic commentary based on the scores
    let trustComment = "";
    if (ti < 25) {
        trustComment = " With a critically low Trust Index of " + ti.toFixed(1) + "%, this video is considered to be actively spreading a false message.";
    } else if (ti < 50) {
        trustComment = " With a low Trust Index of " + ti.toFixed(1) + "%, the factual basis of the claims is weak.";
    } else {
        trustComment = " The video maintains a solid Trust Index of " + ti.toFixed(1) + "%.";
    }
    
    let manipComment = "";
    if (ms_pct > 70) {
        manipComment = " The manipulation risk is critically high (" + ms_pct.toFixed(1) + "%), indicating heavy reliance on deceptive rhetoric or fear-mongering.";
    } else if (ms_pct > 40) {
        manipComment = " The manipulation risk is elevated (" + ms_pct.toFixed(1) + "%), showing notable use of emotional or biased language.";
    } else {
        manipComment = " Manipulation risk is low (" + ms_pct.toFixed(1) + "%), showing standard, neutral language.";
    }
    
    let viralComment = "";
    if (vs_pct >= 80) {
        viralComment = " Additionally, the video is spreading at an explosive rate (" + vs_pct.toFixed(1) + "% virality), making it a high-priority concern for rapid misinformation spread.";
    } else if (vs_pct >= 50) {
        viralComment = " Additionally, the video has gone fairly viral (" + vs_pct.toFixed(1) + "% virality), gaining significant traction and reaching a wide audience quickly.";
    } else if (vs_pct >= 25) {
        viralComment = " It has achieved moderate social media circulation (" + vs_pct.toFixed(1) + "% virality).";
    } else {
        viralComment = " Its current social media spread and virality remains low (" + vs_pct.toFixed(1) + "%).";
    }
    
    const finalExplanation = explanation + trustComment + manipComment + viralComment;
    
    const extVerdictCard = document.getElementById('ext-verdict-card');
    const extBadgeEl = document.getElementById('ext-verdict-badge');
    const extTitleEl = document.getElementById('ext-verdict-title');
    const extExplanationEl = document.getElementById('ext-verdict-explanation');
    
    if (extVerdictCard && extBadgeEl && extTitleEl && extExplanationEl) {
        extBadgeEl.textContent = category;
        extBadgeEl.style.color = verdictColor;
        extBadgeEl.style.borderColor = verdictColor;
        extTitleEl.textContent = verdictTitle;
        extExplanationEl.textContent = finalExplanation;
        extVerdictCard.style.display = "block";
        // Also update trust category badge in metric card
        const catTrustEl = document.getElementById('cat-trust');
        if (catTrustEl) {
            catTrustEl.textContent = category;
            console.log('Category badge updated to:', category);
        }
    }
    
    // Claims
    const claimsList = document.getElementById('claims-list');
    if (data.claims && data.claims.length > 0) {
      claimsList.innerHTML = data.claims.map(c => {
        const text = c.text || "Unknown Claim";
        const verdict = c.nli ? c.nli.verdict : (c.evidence_confidence === 0.0 ? "No Factual Claim Detected" : "Pending verification...");
        const link = (c.supporting_source && c.supporting_source.source && c.supporting_source.source !== '#') 
            ? `<a href="${c.supporting_source.source}" target="_blank" style="color:var(--accent); text-decoration:none; font-weight:bold;">[Source]</a>` 
            : '';
            
        let verdictColor = "var(--warn)";
        if (verdict.includes("Contradict")) verdictColor = "var(--danger)";
        if (verdict.includes("Supported") || verdict.includes("True")) verdictColor = "var(--safe)";
        
        let explanationHtml = '';
        if (c.evidence_text) {
          explanationHtml = `
          <div style="font-size: 0.75rem; background: rgba(255,255,255,0.03); border-left: 2px solid var(--accent); padding: 4px 6px; margin-top: 6px; font-style: italic; color: var(--text-dim); line-height: 1.3;">
            <strong>Snippet:</strong> "${c.evidence_text}"
          </div>`;
        } else {
          let msg = 'ℹ️ No matching web evidence found.';
          if (c.supporting_source?.title === 'Verification Skipped') {
            msg = 'ℹ️ Verification Skipped: Only top 4 claims verified.';
          } else if (c.supporting_source?.title === 'No Factual Claim Detected') {
            msg = 'ℹ️ Subjective / low verifiability statement.';
          } else if (c.nli) {
            msg = `ℹ️ Evidence found: ${c.supporting_source?.title || 'web search'}.`;
          }
          explanationHtml = `
          <div style="font-size: 0.7rem; color: var(--muted); margin-top: 4px; line-height: 1.3;">
            ${msg}
          </div>`;
        }
        
        return `
        <div class="claim-item" style="border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 10px;">
          <div style="font-size: 0.85rem; line-height: 1.4; color: var(--text); margin-bottom: 6px;">
            <strong>Claim:</strong> ${text}
          </div>
          <div style="font-size: 0.75rem; display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <span style="color: ${verdictColor}; font-weight: 500;">${verdict}</span>
            ${link}
          </div>
          ${explanationHtml}
        </div>
        `;
      }).join('');
    } else {
      claimsList.innerHTML = `<div style="color:var(--muted); font-style:italic;">No explicit factual claims detected.</div>`;
    }
  }
});
