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
let selectedFiles = [];
let callTimer = null;
let callSeconds = 0;
let localStream = null;

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
            messages[activePeer.username] = (data.messages || []).map(m => ({
                text: m.text || '',
                time: new Date(m.timestamp * 1000).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
                sent: m.from === 'me'
            }));
        }
    } catch (e) {
        // fallback: keep existing messages
    }

    renderMessages();
    messagesArea.querySelector('.empty-state')?.remove();
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
        <div class="message ${msg.sent ? 'sent' : 'received'}">
            ${!msg.sent ? `
                <div class="message-avatar">
                    <span>${getInitials(activePeer.ip)}</span>
                </div>
            ` : ''}
            <div class="message-content">
                <div class="message-bubble">${msg.text}</div>
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
        selectedFiles.forEach(file => {
            messages[activePeer.username].push({ text: `📎 ${file.name}`, time, sent: true });
        });
        selectedFiles = [];
        filePreview.classList.add('hidden');
        filePreview.innerHTML = '';
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
    const files = Array.from(e.target.files);
    selectedFiles = [...selectedFiles, ...files];
    
    if (selectedFiles.length > 0) {
        filePreview.classList.remove('hidden');
        filePreview.innerHTML = selectedFiles.map((file, index) => `
            <div class="file-item">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M13 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V9L13 2Z" stroke="currentColor" stroke-width="2"/>
                    <path d="M13 2V9H20" stroke="currentColor" stroke-width="2"/>
                </svg>
                <span>${file.name}</span>
                <button class="file-remove" data-index="${index}">✕</button>
            </div>
        `).join('');
        
        document.querySelectorAll('.file-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                const index = parseInt(btn.dataset.index);
                selectedFiles.splice(index, 1);
                
                if (selectedFiles.length === 0) {
                    filePreview.classList.add('hidden');
                    filePreview.innerHTML = '';
                } else {
                    fileInput.dispatchEvent(new Event('change'));
                }
            });
        });
    }
    
    fileInput.value = '';
});

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