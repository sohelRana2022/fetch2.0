// --- Elements ---
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const resultsContainer = document.getElementById('resultsContainer');
const suggestionsContainer = document.getElementById('suggestionsContainer');
const infoContainer = document.getElementById('infoContainer');

// --- Search Function ---
searchBtn.addEventListener('click', () => {
    const query = searchInput.value.trim();
    if (!query) return;
    searchVideos(query);
});

async function searchVideos(query, pageToken = '') {
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query, pageToken })
        });
        const data = await response.json();
        renderSearchResults(data.results);
    } catch (err) {
        console.error(err);
    }
}

function renderSearchResults(results) {
    resultsContainer.innerHTML = '';
    results.forEach(video => {
        const div = document.createElement('div');
        div.className = 'video-result';
        div.innerHTML = `
            <img src="${video.thumbnail}" width="120">
            <p>${video.title}</p>
            <button onclick="fetchVideoInfo('${video.url}')">Select</button>
        `;
        resultsContainer.appendChild(div);
    });
}

// --- Suggestions ---
searchInput.addEventListener('input', async () => {
    const query = searchInput.value.trim();
    if (!query) {
        suggestionsContainer.innerHTML = '';
        return;
    }
    try {
        const response = await fetch('/api/suggestions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query })
        });
        const data = await response.json();
        renderSuggestions(data.results);
    } catch (err) {
        console.error(err);
    }
});

function renderSuggestions(suggestions) {
    suggestionsContainer.innerHTML = '';
    suggestions.forEach(s => {
        const div = document.createElement('div');
        div.className = 'suggestion';
        div.textContent = s;
        div.onclick = () => {
            searchInput.value = s;
            searchBtn.click();
        };
        suggestionsContainer.appendChild(div);
    });
}

// --- Video Info ---
async function fetchVideoInfo(url) {
    try {
        const response = await fetch('/api/info', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ url })
        });
        const data = await response.json();
        renderVideoInfo(data);
    } catch (err) {
        console.error(err);
    }
}

function renderVideoInfo(info) {
    infoContainer.innerHTML = `
        <h3>${info.title}</h3>
        <img src="${info.thumbnail}" width="200">
        <p>Duration: ${Math.floor(info.duration / 60)}:${info.duration % 60}</p>
        ${info.formats.map(f => `<button onclick="startDownload('${info.original_url}', '${f.id}')">${f.label}</button>`).join(' ')}
    `;
}

// --- Download Task ---
async function startDownload(url, quality) {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ url, quality })
        });
        const data = await response.json();
        if (data.task_id) {
            monitorTask(data.task_id, quality);
        }
    } catch (err) {
        console.error(err);
    }
}

// --- Monitor Task Progress ---
function monitorTask(taskId, quality) {
    const progressDiv = document.createElement('div');
    progressDiv.id = `task-${taskId}`;
    progressDiv.innerHTML = `Downloading... <span id="progress-${taskId}">0%</span>`;
    infoContainer.appendChild(progressDiv);

    const interval = setInterval(async () => {
        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            const task = data[taskId];
            if (!task) return;

            document.getElementById(`progress-${taskId}`).textContent = `${task.progress}%`;

            if (task.status === 'finished') {
                clearInterval(interval);
                document.getElementById(`progress-${taskId}`).textContent = `100% - Complete`;
                downloadFile(task, quality);
            }
            if (task.status === 'error') {
                clearInterval(interval);
                document.getElementById(`progress-${taskId}`).textContent = `Error: ${task.error}`;
            }
        } catch (err) {
            console.error(err);
        }
    }, 1500);
}

// --- File Download (with Mobile Path Selection if possible) ---
async function downloadFile(task, quality) {
    const fileName = `download_${task.id}.${quality === 'mp3' ? 'mp3' : 'mp4'}`;
    const downloadUrl = `/api/get_file/${task.id}`;

    if (window.showSaveFilePicker) {
        try {
            const options = {
                suggestedName: fileName,
                types: [
                    {
                        description: quality.toUpperCase(),
                        accept: { [`video/${quality === 'mp3' ? 'mpeg' : 'mp4'}`]: [`.${quality === 'mp3' ? 'mp3' : 'mp4'}`] },
                    },
                ],
            };
            const handle = await window.showSaveFilePicker(options);
            const writable = await handle.createWritable();
            const response = await fetch(downloadUrl);
            const blob = await response.blob();
            await writable.write(blob);
            await writable.close();
            alert('Download complete!');
        } catch (err) {
            console.error('Error saving file:', err);
            fallbackDownload();
        }
    } else {
        fallbackDownload();
    }

    function fallbackDownload() {
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }
}

