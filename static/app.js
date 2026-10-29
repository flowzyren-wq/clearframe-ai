(() => {
  const input = document.getElementById('file-input');
  const dropzone = document.getElementById('dropzone');
  const selected = document.getElementById('selected-file');
  const button = document.getElementById('start-button');
  const strength = document.getElementById('strength');
  const strengthValue = document.getElementById('strength-value');
  const audioOption = document.getElementById('audio-option');
  const jobCard = document.getElementById('job-card');
  const state = document.getElementById('job-state');
  const percent = document.getElementById('job-percent');
  const message = document.getElementById('job-message');
  const progress = document.getElementById('progress-bar');
  const errorBox = document.getElementById('job-error');
  const download = document.getElementById('download-link');
  const reset = document.getElementById('reset-button');
  let selectedFile = null;
  let timer = null;

  const videoExts = new Set(['mp4', 'mov', 'm4v', 'mkv', 'webm']);
  const maxBytes = Number(document.body.dataset.maxUploadMb || 512) * 1024 * 1024;

  function setFile(file) {
    if (!file) return;
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    if (!['jpg', 'jpeg', 'png', 'webp', ...videoExts].includes(ext)) {
      selectedFile = null;
      selected.hidden = true;
      showError('Format belum didukung. Pilih JPG, PNG, WebP, MP4, MOV, M4V, MKV, atau WebM.');
      return;
    }
    if (file.size > maxBytes) {
      selectedFile = null;
      selected.hidden = true;
      showError(`Ukuran file melewati batas ${Math.floor(maxBytes / 1048576)} MB.`);
      return;
    }
    selectedFile = file;
    selected.hidden = false;
    selected.textContent = `${file.name} · ${formatBytes(file.size)}`;
    audioOption.hidden = !videoExts.has(ext);
    button.disabled = false;
    button.querySelector('span:first-child').textContent = 'Tingkatkan file';
    errorBox.hidden = true;
    jobCard.hidden = true;
  }

  function formatBytes(bytes) {
    return bytes < 1048576 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
  }

  function showError(text) {
    jobCard.hidden = false;
    state.textContent = 'PERIKSA FILE';
    state.dataset.state = 'error';
    percent.textContent = '';
    progress.style.width = '0%';
    errorBox.textContent = text;
    errorBox.hidden = false;
    download.hidden = true;
    reset.hidden = false;
  }

  input.addEventListener('change', () => setFile(input.files?.[0]));
  dropzone.addEventListener('dragover', (event) => { event.preventDefault(); dropzone.classList.add('dragging'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragging'));
  dropzone.addEventListener('drop', (event) => {
    event.preventDefault(); dropzone.classList.remove('dragging');
    setFile(event.dataTransfer.files?.[0]);
  });
  strength.addEventListener('input', () => { strengthValue.textContent = `${strength.value}%`; });

  async function poll(jobId) {
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Status tugas tidak tersedia.');
      message.textContent = data.message || 'Sedang memproses…';
      const value = Number.isFinite(data.progress) ? data.progress : 0;
      percent.textContent = `${value}%`;
      progress.style.width = `${value}%`;
      state.textContent = data.status === 'complete' ? 'SIAP' : data.status === 'error' ? 'ERROR' : data.status === 'queued' ? 'MENGANTRE' : 'BEKERJA';
      state.dataset.state = data.status;
      if (data.status === 'complete') {
        clearInterval(timer); timer = null;
        download.href = data.download_url;
        download.download = data.output_name;
        download.hidden = false;
        reset.hidden = false;
        button.disabled = false;
        button.querySelector('span:first-child').textContent = 'Tingkatkan file';
      } else if (data.status === 'error') {
        clearInterval(timer); timer = null;
        errorBox.textContent = data.error || 'Pemrosesan gagal. Periksa setup dan coba lagi.';
        errorBox.hidden = false;
        reset.hidden = false;
        button.disabled = false;
        button.querySelector('span:first-child').textContent = 'Tingkatkan file';
      }
    } catch (error) {
      clearInterval(timer); timer = null;
      showError(error.message);
      button.disabled = false;
      button.querySelector('span:first-child').textContent = 'Tingkatkan file';
    }
  }

  button.addEventListener('click', async () => {
    if (!selectedFile) { showError('Pilih satu foto atau video lebih dulu.'); return; }
    const form = new FormData();
    form.append('file', selectedFile);
    form.append('scale', document.querySelector('input[name="scale"]:checked').value);
    form.append('strength', strength.value);
    form.append('keep_audio', document.getElementById('keep-audio').checked ? 'true' : 'false');
    button.disabled = true;
    button.querySelector('span:first-child').textContent = 'Mengunggah…';
    errorBox.hidden = true;
    download.hidden = true;
    reset.hidden = true;
    jobCard.hidden = false;
    state.textContent = 'MENGUNGGAH'; state.dataset.state = 'processing';
    percent.textContent = '—'; progress.style.width = '0%';
    message.textContent = 'Mengirim file ke mesin yang menjalankan ClearFrame…';
    try {
      const response = await fetch('/api/jobs', { method: 'POST', body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'File tidak dapat diproses.');
      button.querySelector('span:first-child').textContent = 'Memproses…';
      timer = setInterval(() => poll(data.id), 1200);
      await poll(data.id);
    } catch (error) {
      showError(error.message);
      button.disabled = false;
      button.querySelector('span:first-child').textContent = 'Tingkatkan file';
    }
  });

  reset.addEventListener('click', () => {
    if (timer) clearInterval(timer);
    timer = null;
    input.value = '';
    selectedFile = null;
    selected.hidden = true;
    audioOption.hidden = true;
    jobCard.hidden = true;
    button.disabled = false;
    button.querySelector('span:first-child').textContent = 'Tingkatkan file';
    progress.style.width = '0%';
  });
})();
