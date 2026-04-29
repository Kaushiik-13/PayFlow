const API_BASE = '';

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const uploadProgress = document.getElementById('upload-progress');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const uploadStatus = document.getElementById('upload-status');
const refreshBtn = document.getElementById('refresh-status-btn');
const resultsPanel = document.getElementById('results-panel');

const ALLOWED_EXTENSIONS = ['.csv', '.parquet', '.json'];
let selectedFile = null;
let pollInterval = null;

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) selectFile(e.target.files[0]);
});

dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
});

function selectFile(file) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
        showUploadStatus('Unsupported format: ' + ext + '. Please use CSV, Parquet, or JSON.', 'error');
        return;
    }
    selectedFile = file;
    uploadBtn.disabled = false;
    dropZone.querySelector('p').textContent = file.name;
}

uploadBtn.addEventListener('click', async () => {
    if (!selectedFile) return;
    uploadBtn.disabled = true;
    uploadProgress.classList.remove('hidden');

    try {
        const presignRes = await fetch(API_BASE + '/upload-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: selectedFile.name,
                content_type: selectedFile.type || 'application/octet-stream'
            })
        });
        if (!presignRes.ok) throw new Error('Failed to get upload URL');
        const data = await presignRes.json();
        const uploadUrl = data.upload_url;

        await uploadFileToS3(selectedFile, uploadUrl);
        showUploadStatus('File uploaded successfully: ' + selectedFile.name, 'success');
        setStepStatus('step-upload', 'complete');
        startPolling();
    } catch (err) {
        showUploadStatus('Upload failed: ' + err.message, 'error');
        uploadBtn.disabled = false;
    }
});

function uploadFileToS3(file, presignedUrl) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', presignedUrl);
        xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                progressFill.style.width = pct + '%';
                progressText.textContent = pct + '%';
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) resolve();
            else reject(new Error('S3 upload failed: ' + xhr.status));
        };
        xhr.onerror = () => reject(new Error('S3 upload network error'));
        xhr.send(file);
    });
}

refreshBtn.addEventListener('click', fetchPipelineStatus);

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    fetchPipelineStatus();
    pollInterval = setInterval(fetchPipelineStatus, 10000);
}

async function fetchPipelineStatus() {
    try {
        const res = await fetch(API_BASE + '/pipeline-status');
        if (!res.ok) throw new Error('Status check failed');
        const data = await res.json();

        var stepIdMap = {
            'upload': 'step-upload',
            'glue_etl': 'step-etl',
            'crawlers': 'step-crawler',
            'anomaly_detection': 'step-anomaly'
        };
        for (var i = 0; i < data.stages.length; i++) {
            var stage = data.stages[i];
            var stepId = stepIdMap[stage.name];
            if (stepId) setStepStatus(stepId, stage.status);
        }

        var anomalyStage = null;
        for (var j = 0; j < data.stages.length; j++) {
            if (data.stages[j].name === 'anomaly_detection') {
                anomalyStage = data.stages[j];
                break;
            }
        }
        if (anomalyStage && anomalyStage.status === 'complete') {
            clearInterval(pollInterval);
            fetchResults();
        }
    } catch (err) {
        console.error('Status poll error:', err);
    }
}

function setStepStatus(stepId, status) {
    var el = document.getElementById(stepId);
    if (!el) return;
    var statusEl = el.querySelector('.step-status');
    statusEl.textContent = status;
    statusEl.className = 'step-status ' + status;
}

async function fetchResults() {
    try {
        var res = await fetch(API_BASE + '/results');
        if (!res.ok) throw new Error('Results fetch failed');
        var data = await res.json();

        resultsPanel.classList.remove('hidden');
        document.getElementById('res-total').textContent = data.summary.total_scored.toLocaleString();
        document.getElementById('res-anomalies').textContent = data.summary.anomalies_detected.toLocaleString();
        document.getElementById('res-rate').textContent = data.summary.anomaly_rate_pct + '%';
        document.getElementById('res-source').textContent = data.summary.source_file || '-';

        if (data.top_anomalies && data.top_anomalies.length > 0) {
            var headers = Object.keys(data.top_anomalies[0]);
            var headerRow = document.getElementById('anomalies-header');
            var tbody = document.getElementById('anomalies-body');
            var headerHtml = '';
            for (var h = 0; h < headers.length; h++) {
                headerHtml += '<th>' + headers[h] + '</th>';
            }
            headerRow.innerHTML = headerHtml;
            var bodyHtml = '';
            for (var i = 0; i < Math.min(data.top_anomalies.length, 100); i++) {
                bodyHtml += '<tr>';
                for (var k = 0; k < headers.length; k++) {
                    var val = data.top_anomalies[i][headers[k]];
                    bodyHtml += '<td>' + (val != null ? val : '-') + '</td>';
                }
                bodyHtml += '</tr>';
            }
            tbody.innerHTML = bodyHtml;
        }
    } catch (err) {
        console.error('Results fetch error:', err);
    }
}

document.getElementById('download-csv-btn').addEventListener('click', () => {
    window.open(API_BASE + '/results?download=true', '_blank');
});

function showUploadStatus(msg, type) {
    uploadStatus.classList.remove('hidden', 'success', 'error');
    uploadStatus.classList.add(type);
    uploadStatus.textContent = msg;
}