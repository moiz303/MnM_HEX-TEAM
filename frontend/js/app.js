// Active peers (populated from backend /api/peers). Keep mock fallback if API unavailable.
let peers = [];

const mockPeers = [
    { id: 1, ip: '192.168.1.102', username: '192.168.1.102', ping: 12, online: true },
    { id: 2, ip: '192.168.1.105', username: '192.168.1.105', ping: 8, online: true },
    { id: 3, ip: '192.168.1.110', username: '192.168.1.110', ping: 25, online: false },
    { id: 4, ip: '192.168.1.115', username: '192.168.1.115', ping: 15, online: true },
    { id: 5, ip: '192.168.1.120', username: '192.168.1.120', ping: 30, online: true },
    { id: 6, ip: '192.168.1.125', username: '192.168.1.125', ping: 18, online: false },
    { id: 7, ip: '192.168.1.130', username: '192.168.1.130', ping: 22, online: true }
];

const randomResponses = [
    'Окей',
    'Понял',
    'Хорошо',
    'Сделано',
    'Ясно',
    'Договорились',
    'Без проблем',
    'Согласен',
    'Отлично!',
    'Супер',
    'Есть',
    'Принято',
    'Конечно',
    'Все понятно',
    'Буду делать'
];

let activePeer = null;
let messages = {};
let selectedFiles = []; // array of {file, uid}
let callTimer = null;
let callSeconds = 0;
let localStream = null;
let messagesPollInterval = null;
let transfersPollInterval = null;
let activeTransfers = {}; // track transfer progress

const peersList = document.getElementById('peers-list');
const messagesArea = document.getElementById('messages-area');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const searchInput = document.getElementById('search-input');
const headerAvatar = document.getElementById('header-avatar');
const headerName = document.getElementById('header-name');
const headerStatus = document.getElementById('header-status');
const voiceCallBtn = document.getElementById('voice-call-btn');
const videoCallBtn = document.getElementById('video-call-btn');
const deleteChatBtn = document.getElementById('delete-chat-btn');
const callModal = document.getElementById('call-modal');
const callAvatarText = document.getElementById('call-avatar-text');
const callName = document.getElementById('call-name');
const callStatus = document.getElementById('call-status');
const declineCallBtn = document.getElementById('decline-call-btn');
const callContent = document.getElementById('call-content');
const videoCallWrapper = document.getElementById('video-call-wrapper');
const videoTimer = document.getElementById('video-timer');
const videoEndBtn = document.getElementById('video-end-btn');
const localVideo = document.getElementById('local-video');
const remoteVideo = document.getElementById('remote-video');
const attachBtn = document.getElementById('attach-btn');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');

function getInitials(ip) {
    const parts = ip.split('.');
    return parts[parts.length - 1];
}

function isImageUrl(url) {
    return /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(url);
}

function saveMessagesToStorage(username) {
    try {
        localStorage.setItem(`chat_${username}`, JSON.stringify(messages[username] || []));
    } catch (e) {
        // ignore storage errors
    }
}

function loadMessagesFromStorage(username) {
    try {
        const raw = localStorage.getItem(`chat_${username}`);
        if (raw) {
            return JSON.parse(raw);
        }
    } catch (e) {}
    return null;
}

async function fetchPeersPolling() {
    try {
        const res = await fetch('/api/peers');
        if (!res.ok) throw new Error('fetch failed');
        const data = await res.json();
        // Map backend peers to UI shape
        peers = (data.peers || []).map((p, idx) => ({
            id: p.username || p.ip || idx,
            username: p.username || p.ip,
            ip: p.ip || p.username,
            ping: Math.floor(Math.random() * 40) + 5,
            online: p.status === 'online',
            has_chat: p.has_chat || false
        }));
    } catch (err) {
        // fallback to mock if API unavailable
        peers = mockPeers;
    }

    renderPeers(searchInput.value);

    if (activePeer) {
        const updated = peers.find(p => p.username === activePeer.username || p.id === activePeer.id);
        if (updated) {
            activePeer = updated;
            updateHeader();
        }
    }
}

// Poll transfers every 2 seconds
function startTransfersPolling() {
    if (transfersPollInterval) clearInterval(transfersPollInterval);
    transfersPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/transfers');
            if (!res.ok) return;
            const data = await res.json();
            
            // Update active transfers with latest status
            data.transfers.forEach(transfer => {
                const existing = activeTransfers[transfer.transfer_id];
                if (!existing || existing.status !== transfer.status || existing.progress !== transfer.progress) {
                    activeTransfers[transfer.transfer_id] = transfer;
                    updateTransferUI(transfer);
                    
                    // Show completion notification
                    if (transfer.status === 'completed' && (!existing || existing.status !== 'completed')) {
                        showTransferNotification(transfer, 'completed');
                    } else if (transfer.status === 'failed' && (!existing || existing.status !== 'failed')) {
                        showTransferNotification(transfer, 'failed');
                    }
                }
            });
            
            // Clean up completed/failed transfers after 10 seconds
            Object.keys(activeTransfers).forEach(id => {
                const transfer = activeTransfers[id];
                if ((transfer.status === 'completed' || transfer.status === 'failed') && 
                    Date.now() - transfer.updated_at > 10000) {
                    delete activeTransfers[id];
                }
            });
        } catch (e) {
            // ignore polling errors
        }
    }, 2000);
}

function updateTransferUI(transfer) {
    // Update progress bars in file preview
    const bar = document.querySelector(`.file-item[data-transfer-id="${transfer.transfer_id}"] .file-progress-bar`);
    if (bar) {
        bar.style.width = `${Math.round(transfer.progress || 0)}%`;
        if (transfer.status === 'completed') {
            bar.style.background = 'linear-gradient(90deg, #4CAF50, #4CAF50)';
        } else if (transfer.status === 'failed') {
            bar.style.background = 'linear-gradient(90deg, #f44336, #f44336)';
        }
    }
    
    // Update file preview items with transfer status
    const item = document.querySelector(`.file-item[data-transfer-id="${transfer.transfer_id}"]`);
    if (item) {
        item.dataset.status = transfer.status;
        const statusText = item.querySelector('.file-status');
        if (statusText) {
            statusText.textContent = getTransferStatusText(transfer.status);
        }
    }
}

function getTransferStatusText(status) {
    switch (status) {
        case 'pending': return 'Ожидание...';
        case 'in_progress': return 'Передача...';
        case 'completed': return 'Завершено';
        case 'failed': return 'Ошибка';
        case 'cancelled': return 'Отменено';
        default: return status;
    }
}

function showTransferNotification(transfer, type) {
    const message = type === 'completed' 
        ? `📁 Файл "${transfer.filename}" успешно передан`
        : `❌ Передача файла "${transfer.filename}" не удалась: ${transfer.error || 'Неизвестная ошибка'}`;
    
    // Add as system message to current chat if available
    if (activePeer && messages[activePeer.username]) {
        messages[activePeer.username].push({
            text: message,
            time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
            sent: false,
            system: true
        });
        renderMessages();
    }
}

// Start transfer polling when page loads
startTransfersPolling();

// Poll peers every 3s
fetchPeersPolling();
setInterval(fetchPeersPolling, 3000);

function renderPeers(filter = '') {
    const filtered = peers.filter(p => (p.ip || p.username || '').includes(filter));

    peersList.innerHTML = filtered.map(peer => `
        <div class="peer-item ${activePeer?.id === peer.id ? 'active' : ''}" data-peer-username="${peer.username}">
            <div class="avatar">
                <span>${getInitials(peer.ip)}</span>
                <div class="status-indicator ${peer.online ? 'online' : 'offline'}"></div>
            </div>
            <div class="peer-info">
                <h4>${peer.ip}</h4>
                <div class="peer-meta">
                    <span class="peer-ping">
                        <span class="ping-dot ${peer.online ? 'online' : 'offline'}"></span>
                        ${peer.ping}ms
                    </span>
                </div>
            </div>
        </div>
    `).join('');

    document.querySelectorAll('.peer-item').forEach(item => {
        item.addEventListener('click', () => {
            const username = item.dataset.peerUsername;
            selectPeerByUsername(username);
        });
    });
}

async function selectPeerByUsername(username) {
    activePeer = peers.find(p => p.username === username);
    if (!activePeer) return;

    // ensure messages bucket
    if (!messages[activePeer.username]) messages[activePeer.username] = [];

    // try to load local cached messages first so UI works frontend-only
    const local = loadMessagesFromStorage(activePeer.username);
    if (local && Array.isArray(local) && local.length > 0) {
        messages[activePeer.username] = local;
        renderMessages();
    }

    renderPeers(searchInput.value);
    updateHeader();

    // If no active chat, try to initiate handshake
    if (!activePeer.has_chat) {
        try {
            const res = await fetch('/api/start_chat', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: activePeer.username })
            });
            if (res.ok) {
                activePeer.has_chat = true;
            }
        } catch (e) {
            // ignore
        }
    }

    // Load message history from backend
    try {
        const url = new URL('/api/get_messages', window.location.origin);
        url.searchParams.set('peer', activePeer.username);
        const r = await fetch(url);
        if (r.ok) {
            const data = await r.json();
            // map messages to simple structure
            const mapped = (data.messages || []).map(m => ({
                text: m.text || '',
                time: new Date(m.timestamp * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
                sent: m.from === 'me'
            }));
            // If backend provides only encrypted placeholders, keep local cache.
            const hasReal = mapped.some(x => x.text && x.text !== '[encrypted]');
            if (hasReal) {
                messages[activePeer.username] = mapped.reverse();
            }
        }
    } catch (e) {
        // fallback: keep existing messages
    }

    renderMessages();
    messagesArea.querySelector('.empty-state')?.remove();

    // start polling messages for this peer
    if (messagesPollInterval) clearInterval(messagesPollInterval);
    messagesPollInterval = setInterval(async () => {
        try {
            const url = new URL('/api/get_messages', window.location.origin);
            url.searchParams.set('peer', activePeer.username);
            const r = await fetch(url);
            if (!r.ok) return;
            const data = await r.json();
            const mapped = (data.messages || []).map(m => ({
                id: m.msg_id || `${m.timestamp}_${Math.random()}`,
                text: m.text || '',
                time: new Date(m.timestamp * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
                sent: m.from === 'me'
            }));

            // merge deduplicated (by id)
            const existing = messages[activePeer.username] || [];
            const existingIds = new Set(existing.map(x => x.id));
            const merged = existing.concat(mapped.filter(x => !existingIds.has(x.id)));
            // sort by time (we store in chronological order)
            merged.sort((a, b) => a.time.localeCompare(b.time));
            messages[activePeer.username] = merged;
            renderMessages();
        } catch (e) {
            // ignore polling errors
        }
    }, 2000);
}

function updateHeader() {
    if (!activePeer) return;

    headerAvatar.innerHTML = `
        <span>${getInitials(activePeer.ip)}</span>
        <div class="status-indicator ${activePeer.online ? 'online' : 'offline'}"></div>
    `;
    headerName.textContent = activePeer.ip;
    headerStatus.textContent = `${activePeer.ping}ms`;
}

function renderMessages() {
    if (!activePeer || !messages[activePeer.username]) return;

    const msgs = messages[activePeer.username];

    messagesArea.innerHTML = msgs.map(msg => `
        <div class="message ${msg.system ? 'system' : (msg.sent ? 'sent' : 'received')}">
            ${!msg.sent && !msg.system ? `
                <div class="message-avatar">
                    <span>${getInitials(activePeer.ip)}</span>
                </div>
            ` : ''}
            <div class="message-content">
                <div class="message-bubble">${(() => {
                    const text = msg.text || '';
                    // find first URL-like token
                    const m = text.match(/(https?:\/\/\S+|\/uploads\/\S+|\/downloads\/\S+)/);
                    if (m) {
                        const url = m[0];
                        if (isImageUrl(url)) {
                            return `<img src="${url}" class="msg-image" />`;
                        }
                        // fallback: show link and remaining text
                        const rest = text.replace(url, '').trim();
                        return `<a href="${url}" target="_blank">${url}</a>${rest ? ' ' + rest : ''}`;
                    }
                    // no url -> plain text (escape minimal)
                    return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                })()}</div>
                <span class="message-time">${msg.time}</span>
            </div>
            ${msg.sent ? `
                <div class="message-avatar">
                    <span>Я</span>
                </div>
            ` : ''}
        </div>
    `).join('');

    messagesArea.scrollTop = messagesArea.scrollHeight;
    // save to localStorage for offline/frontend-only use
    saveMessagesToStorage(activePeer.username);
}

function sendMessage() {
    if (!activePeer || (!messageInput.value.trim() && selectedFiles.length === 0)) return;

    const text = messageInput.value.trim();
    const now = new Date();
    const time = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

    // locally append
    if (text) {
        if (!messages[activePeer.username]) messages[activePeer.username] = [];
        messages[activePeer.username].push({ text, time, sent: true });
    }

    if (selectedFiles.length > 0) {
        // append placeholders to message list
        selectedFiles.forEach(item => {
            messages[activePeer.username].push({ text: `📎 ${item.file.name}`, time, sent: true });
        });
        // do not clear preview yet — we'll upload and then clear
    }

    messageInput.value = '';
    renderMessages();

    // Send to backend
    if (text) {
        fetch('/api/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ peer: activePeer.username, text })
        }).catch(() => {
            // ignore send errors for now
        });
    }

    // If there are files, upload them in chunks and send link
    if (selectedFiles.length > 0) {
        (async () => {
            for (const item of selectedFiles.slice()) {
                const file = item.file;
                const uid = item.uid;
                try {
                    const res = await uploadFileInChunks(file, activePeer.username, (p) => {
                        // update progress bar in UI
                        const bar = document.querySelector(`.file-item[data-uid="${uid}"] .file-progress-bar`);
                        if (bar) bar.style.width = `${Math.round(p * 100)}%`;
                    });

                    if (res && res.upload_id) {
                        // try P2P send
                        try {
                            const sendRes = await fetch('/api/send_uploaded_file', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ upload_id: res.upload_id, peer: activePeer.username })
                            });
                            if (sendRes.ok) {
                                const sendData = await sendRes.json();
                                if (sendData.transfer_id) {
                                    // Track this transfer
                                    activeTransfers[sendData.transfer_id] = {
                                        transfer_id: sendData.transfer_id,
                                        filename: file.name,
                                        status: 'pending',
                                        progress: 0,
                                        direction: 'upload'
                                    };
                                    
                                    // Update UI to show transfer tracking
                                    const fileItem = document.querySelector(`.file-item[data-uid="${uid}"]`);
                                    if (fileItem) {
                                        fileItem.dataset.transferId = sendData.transfer_id;
                                        const statusDiv = document.createElement('div');
                                        statusDiv.className = 'file-status';
                                        statusDiv.textContent = 'Ожидание...';
                                        fileItem.appendChild(statusDiv);
                                    }
                                }
                            } else {
                                console.warn('P2P send failed, falling back to link');
                                // fallback to sending link stored in res.file_url
                                if (res.file_url) {
                                    const fileMsg = `📎 ${file.name} ${res.file_url}`;
                                    fetch('/api/send_message', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ peer: activePeer.username, text: fileMsg })
                                    }).catch(() => {});
                                }
                            }
                        } catch (err) {
                            console.error('Send file failed', err);
                            if (res.file_url) {
                                const fileMsg = `📎 ${file.name} ${res.file_url}`;
                                fetch('/api/send_message', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ peer: activePeer.username, text: fileMsg })
                                }).catch(() => {});
                            }
                        }
                    }
                } catch (err) {
                    console.error('Upload failed', err);
                    const bar = document.querySelector(`.file-item[data-uid="${uid}"] .file-progress-bar`);
                    if (bar) bar.style.background = 'linear-gradient(90deg, var(--color-error), var(--color-error))';
                }
            }

            // after all uploads, clear selection and hide preview
            selectedFiles = [];
            filePreview.classList.add('hidden');
            filePreview.innerHTML = '';
        })();
    }

    // Simulate reply only if using mock backend
    if (peers === mockPeers) {
        setTimeout(() => {
            const randomResponse = randomResponses[Math.floor(Math.random() * randomResponses.length)];
            messages[activePeer.username].push({ text: randomResponse, time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }), sent: false });
            renderMessages();
        }, 500 + Math.random() * 1500);
    }
}

function deleteChat() {
    if (!activePeer) return;
    
    if (confirm(`Удалить чат с ${activePeer.ip}?`)) {
        messages[activePeer.id] = [];
        renderMessages();
    }
}

function startVoiceCall() {
    if (!activePeer) return;
    
    callModal.classList.remove('hidden');
    callContent.classList.remove('hidden');
    videoCallWrapper.classList.add('hidden');
    
    callAvatarText.textContent = getInitials(activePeer.ip);
    callName.textContent = activePeer.ip;
    callStatus.textContent = 'Звонок...';
    
    setTimeout(() => {
        callStatus.textContent = 'Соединение...';
    }, 2000);
    
    setTimeout(() => {
        startCallTimer();
    }, 4000);
}

async function startVideoCall() {
    if (!activePeer) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Браузер не поддерживает доступ к камере');
        return;
    }

    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true
        });

        localVideo.srcObject = localStream;
        localVideo.muted = true;
        localVideo.playsInline = true;

        callModal.classList.remove('hidden');
        callContent.classList.remove('hidden');
        videoCallWrapper.classList.add('hidden');

        callAvatarText.textContent = getInitials(activePeer.ip);
        callName.textContent = activePeer.ip;
        callStatus.textContent = 'Видеозвонок...';

        setTimeout(() => {
            callStatus.textContent = 'Соединение...';
        }, 2000);

        setTimeout(() => {
            callContent.classList.add('hidden');
            videoCallWrapper.classList.remove('hidden');

            remoteVideo.poster = '';
            remoteVideo.removeAttribute('src');
            remoteVideo.load();

            startCallTimer();
        }, 4000);
    } catch (error) {
        if (error.name === 'NotAllowedError') {
            alert('Доступ к камере запрещён');
        } else if (error.name === 'NotFoundError') {
            alert('Камера не найдена');
        } else {
            alert('Не удалось получить доступ к камере');
        }
    }
}

function startCallTimer() {
    callSeconds = 0;
    updateTimerDisplay();
    
    callTimer = setInterval(() => {
        callSeconds++;
        updateTimerDisplay();
    }, 1000);
}

function updateTimerDisplay() {
    const minutes = Math.floor(callSeconds / 60);
    const seconds = callSeconds % 60;
    const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    
    if (videoCallWrapper.classList.contains('hidden')) {
        callStatus.textContent = timeStr;
    } else {
        videoTimer.textContent = timeStr;
    }
}

function endCall() {
    callModal.classList.add('hidden');
    callContent.classList.remove('hidden');
    videoCallWrapper.classList.add('hidden');
    callStatus.textContent = 'Звонок...';
    
    if (callTimer) {
        clearInterval(callTimer);
        callTimer = null;
    }
    
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
    
    callSeconds = 0;
}

attachBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files).map(f => ({ file: f, uid: `${Date.now()}_${Math.floor(Math.random()*1000000)}` }));
    selectedFiles = [...selectedFiles, ...files];

    if (selectedFiles.length > 0) {
        filePreview.classList.remove('hidden');
        filePreview.innerHTML = selectedFiles.map((item) => `
            <div class="file-item" data-uid="${item.uid}">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M13 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V9L13 2Z" stroke="currentColor" stroke-width="2"/>
                    <path d="M13 2V9H20" stroke="currentColor" stroke-width="2"/>
                </svg>
                <span>${item.file.name}</span>
                <div class="file-progress"><div class="file-progress-bar" style="width:0%"></div></div>
                <button class="file-remove" data-uid="${item.uid}">✕</button>
            </div>
        `).join('');

        // remove handlers
        document.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const uid = btn.dataset.uid;
                const idx = selectedFiles.findIndex(s => s.uid === uid);
                if (idx !== -1) selectedFiles.splice(idx, 1);

                if (selectedFiles.length === 0) {
                    filePreview.classList.add('hidden');
                    filePreview.innerHTML = '';
                } else {
                    // re-render
                    fileInput.dispatchEvent(new Event('change'));
                }
            });
        });
    }

    fileInput.value = '';
});

/**
 * Upload a file in chunks to the backend.
 * Calls /api/upload/init -> /api/upload/chunk -> /api/upload/complete
 * Returns {file_url, filename} on success.
 */
async function uploadFileInChunks(file, peerUsername, onProgress) {
    const MAX_SIZE = 200 * 1024 * 1024; // 200MB
    if (file.size > MAX_SIZE) throw new Error('File exceeds 200MB limit');

    // Init upload
    const initRes = await fetch('/api/upload/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, size: file.size })
    });
    if (!initRes.ok) throw new Error('Failed to init upload');
    const initData = await initRes.json();
    const uploadId = initData.upload_id;

    const CHUNK_SIZE = 512 * 1024; // 512 KB
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const blob = file.slice(start, end);

        const form = new FormData();
        form.append('upload_id', uploadId);
        form.append('index', String(i));
        form.append('chunk', blob, file.name);

        const chunkRes = await fetch('/api/upload/chunk', {
            method: 'POST',
            body: form
        });
        if (!chunkRes.ok) throw new Error('Chunk upload failed');

        if (onProgress) onProgress((i + 1) / totalChunks);
    }

    // Complete
    const completeRes = await fetch('/api/upload/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: uploadId })
    });
    if (!completeRes.ok) throw new Error('Upload complete failed');
    const completeData = await completeRes.json();
    return completeData;
}

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

searchInput.addEventListener('input', (e) => {
    renderPeers(e.target.value);
});

deleteChatBtn.addEventListener('click', deleteChat);
voiceCallBtn.addEventListener('click', startVoiceCall);
videoCallBtn.addEventListener('click', startVideoCall);
declineCallBtn.addEventListener('click', endCall);
videoEndBtn.addEventListener('click', endCall);

renderPeers();