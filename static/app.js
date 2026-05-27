const form = document.getElementById("analyze-form");
const urlInput = document.getElementById("url");
const submitBtn = document.getElementById("submit-btn");
const progressSection = document.getElementById("progress-section");
const progressFill = document.getElementById("progress-fill");
const progressMessage = document.getElementById("progress-message");
const progressStatus = document.getElementById("progress-status");
const errorSection = document.getElementById("error-section");
const errorMessage = document.getElementById("error-message");
const resultsSection = document.getElementById("results-section");
const videoTitle = document.getElementById("video-title");
const videoMeta = document.getElementById("video-meta");
const clipsContainer = document.getElementById("clips-container");

const STATUS_LABELS = {
  queued: "Antrian",
  downloading: "Mengunduh",
  transcribing: "Transkripsi",
  analyzing: "Analisis",
  exporting: "Ekspor",
  done: "Selesai",
  error: "Error",
};

let pollTimer = null;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;

  resetUI();
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(formatApiError(err.detail, "Gagal memulai analisis."));
    }

    const { job_id } = await res.json();
    progressSection.classList.remove("hidden");
    pollJob(job_id);
  } catch (err) {
    showError(err.message);
    submitBtn.disabled = false;
  }
});

function resetUI() {
  progressSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
  clipsContainer.innerHTML = "";
  if (pollTimer) clearInterval(pollTimer);
}

function showError(msg) {
  errorSection.classList.remove("hidden");
  errorMessage.textContent = msg;
  submitBtn.disabled = false;
}

function pollJob(jobId) {
  const poll = async () => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      const data = await res.json();

      progressFill.style.width = `${data.progress}%`;
      progressMessage.textContent = data.message || "Memproses...";
      progressStatus.textContent = STATUS_LABELS[data.status] || data.status;

      if (data.status === "error") {
        clearInterval(pollTimer);
        progressSection.classList.add("hidden");
        showError(data.error || "Terjadi kesalahan.");
        return;
      }

      if (data.status === "done") {
        clearInterval(pollTimer);
        await loadResults(jobId);
        progressSection.classList.add("hidden");
        submitBtn.disabled = false;
      }
    } catch (err) {
      clearInterval(pollTimer);
      showError(err.message);
    }
  };

  poll();
  pollTimer = setInterval(poll, 2000);
}

async function loadResults(jobId) {
  const res = await fetch(`/api/jobs/${jobId}/result`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Gagal memuat hasil.");
  }

  const data = await res.json();
  videoTitle.textContent = data.video_title;
  const duration = data.duration_sec
    ? `Durasi: ${formatTime(data.duration_sec)}`
    : "";
  const shortLabel = data.final_short_url ? "short final tersedia" : "";
  videoMeta.textContent = [duration, `${data.clips.length} clip ditemukan`, shortLabel]
    .filter(Boolean)
    .join(" · ");

  clipsContainer.innerHTML = "";
  if (data.final_short_url) {
    clipsContainer.appendChild(renderFinalShortCard(data.final_short_url));
  }
  for (const clip of data.clips) {
    clipsContainer.appendChild(renderClipCard(clip));
  }

  resultsSection.classList.remove("hidden");
}

function renderFinalShortCard(url) {
  const card = document.createElement("article");
  card.className = "card clip-card";
  card.innerHTML = `
    <div class="clip-media">
      <span class="clip-rank">Short Final</span>
      <video controls preload="metadata" src="${url}"></video>
      <a class="download-btn" href="${url}" download="short.mp4">Unduh Short MP4</a>
    </div>
    <div class="clip-info">
      <h3>Video short gabungan</h3>
      <p class="clip-text">Semua clip terbaik telah digabung ke satu file short.</p>
    </div>
  `;
  return card;
}

function renderClipCard(clip) {
  const card = document.createElement("article");
  card.className = "card clip-card";

  card.innerHTML = `
    <div class="clip-media">
      <span class="clip-rank">#${clip.rank}</span>
      <video controls preload="metadata" src="${clip.mp4_url}"></video>
      <a class="download-btn" href="${clip.mp4_url}" download="clip_${clip.rank}.mp4">Unduh MP4</a>
    </div>
    <div class="clip-info">
      <h3>${escapeHtml(clip.topic)}</h3>
      <p class="clip-time">${clip.start_label} → ${clip.end_label}</p>
      <p class="clip-label">Hook</p>
      <p class="clip-text">${escapeHtml(clip.hook_text)}</p>
      <p class="clip-label">Kesimpulan</p>
      <p class="clip-text">${escapeHtml(clip.conclusion_text)}</p>
      <p class="clip-scores">
        Skor — Hook: ${clip.scores.hook} · Kesimpulan: ${clip.scores.conclusion} · Minat: ${clip.scores.interest} · Total: ${clip.scores.total}
      </p>
    </div>
  `;
  return card;
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatApiError(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return fallback;
}
