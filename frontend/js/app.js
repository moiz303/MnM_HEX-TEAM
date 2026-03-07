let peers = [];
let activePeer = null;
let messages = {};
let selectedFiles = [];
let messagesPollInterval = null;
let currentUsername = localStorage.getItem('messenger_username') || 'user';
let transfersPollInterval = null;
let activeTransfers = {};

console.log('Current username from localStorage:', currentUsername);

class NotificationSystem {
    constructor() {
        this.container = document.getElementById('notification-container');
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;

        const icon = this.getIcon(type);
        const content = document.createElement('div');
        content.className = 'notification-content';
        content.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.className = 'notification-close';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => this.hide(notification);

        notification.appendChild(icon);
        notification.appendChild(content);
        notification.appendChild(closeBtn);

        this.container.appendChild(notification);

        if (duration > 0) {
            setTimeout(() => this.hide(notification), duration);
        }

        return notification;
    }

    getIcon(type) {
        const icon = document.createElement('div');
        icon.className = 'notification-icon';
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        icon.innerHTML = icons[type] || icons.info;
        return icon;
    }

    hide(notification) {
        notification.classList.add('hide');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    success(message, duration) { return this.show(message, 'success', duration); }
    error(message, duration) { return this.show(message, 'error', duration); }
    warning(message, duration) { return this.show(message, 'warning', duration); }
    info(message, duration) { return this.show(message, 'info', duration); }
}

const notifications = new NotificationSystem();

const peersList = document.getElementById('peers-list');
const messagesArea = document.getElementById('messages-area');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const searchInput = document.getElementById('search-input');
const headerName = document.getElementById('header-name');
const headerStatus = document.getElementById('header-status');
const attachBtn = document.getElementById('attach-btn');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const messageInputWrapper = document.getElementById('message-input-wrapper');
const currentUserName = document.getElementById('current-user-name');

function getInitials(name) {
    if (!name) return '?';
    if (name.includes('.')) {
        const parts = name.split('.');
        return parts[parts.length - 1];
    }
    if (name.length <= 2) {
        return name.toUpperCase();
    }
    return name.charAt(0).toUpperCase() + name.charAt(name.length - 1).toUpperCase();
}

function isImageUrl(url) {
    return /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(url);
}

function saveMessagesToStorage(username) {
    try {
        localStorage.setItem(`chat_${username}`, JSON.stringify(messages[username] || []));
    } catch (e) {
        console.error('Storage error:', e);
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function deselectPeer() {
    activePeer = null;
    stopMessagePolling();
    renderMessages();
    renderPeers();
    updateHeader();
}

function stopMessagePolling() {
    if (messagesPollInterval) {
        clearInterval(messagesPollInterval);
        messagesPollInterval = null;
        console.log('Message polling stopped');
    }
}

function startMessagePolling() {
    stopMessagePolling();

    if (activePeer) {
        messagesPollInterval = setInterval(async () => {
            if (!activePeer) {
                stopMessagePolling();
                return;
            }

            try {
                const url = new URL('/api/get_messages', window.location.origin);
                url.searchParams.set('peer', activePeer.username);
                const r = await fetch(url);

                if (r.ok) {
                    const data = await r.json();
                    if (data.messages && data.messages.length > 0) {
                        const mapped = data.messages.map(m => ({
                            id: m.msg_id || m.id || Math.random().toString(36).substr(2, 9),
                            from: m.from || 'unknown',
                            text: m.text || '',
                            time: m.time || new Date(m.timestamp * 1000).toISOString(),
                            sent: m.from === currentUsername || m.from === 'me'
                        }));

                        const existing = messages[activePeer.username] || [];
                        const existingIds = new Set(existing.map(x => x.id));
                        const newMessages = mapped.filter(x => !existingIds.has(x.id));

                        if (newMessages.length > 0) {
                            const merged = existing.concat(newMessages);
                            merged.sort((a, b) => a.time.localeCompare(b.time));
                            messages[activePeer.username] = merged;
                            renderMessages();
                            saveMessagesToStorage(activePeer.username);
                        }
                    }
                } else {
                    const url2 = new URL('/api/get_messages', window.location.origin);
                    url2.searchParams.set('peer', activePeer.ip);
                    const r2 = await fetch(url2);

                    if (r2.ok) {
                        const data = await r2.json();
                        if (data.messages && data.messages.length > 0) {
                            const mapped = data.messages.map(m => ({
                                id: m.msg_id || m.id || Math.random().toString(36).substr(2, 9),
                                from: m.from || 'unknown',
                                text: m.text || '',
                                time: m.time || new Date(m.timestamp * 1000).toISOString(),
                                sent: m.from === currentUsername || m.from === 'me'
                            }));

                            const existing = messages[activePeer.username] || [];
                            const existingIds = new Set(existing.map(x => x.id));
                            const newMessages = mapped.filter(x => !existingIds.has(x.id));

                            if (newMessages.length > 0) {
                                const merged = existing.concat(newMessages);
                                merged.sort((a, b) => a.time.localeCompare(b.time));
                                messages[activePeer.username] = merged;
                                renderMessages();
                                saveMessagesToStorage(activePeer.username);
                            }
                        }
                    }
                }
            } catch (e) {
                console.error('Failed to load messages:', e);
            }
        }, 2000);
    }
}

async function fetchPeersPolling() {
    try {
        const res = await fetch('/api/peers');
        if (!res.ok) throw new Error('fetch failed');

        const data = await res.json();

        peers = (data.peers || []).map((p, idx) => ({
            id: p.username || p.ip || idx,
            username: p.username || p.ip,
            ip: p.ip || p.username,
            ping: Math.floor(Math.random() * 40) + 5,
            online: p.status === 'online',
            has_chat: p.has_chat || false
        }));
    } catch (err) {
        console.warn('Failed to fetch peers:', err);

        if (peers.length === 0) {
            peers = [
                { id: 'test1', username: 'User1', ip: '192.168.1.10', ping: 15, online: true, has_chat: false },
                { id: 'test2', username: 'User2', ip: '192.168.1.11', ping: 23, online: false, has_chat: false }
            ];
        }
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

function startTransfersPolling() {
    if (transfersPollInterval) clearInterval(transfersPollInterval);
    transfersPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/transfers');
            if (!res.ok) return;
            const data = await res.json();

            data.transfers.forEach(transfer => {
                const existing = activeTransfers[transfer.transfer_id];
                if (!existing || existing.status !== transfer.status || existing.progress !== transfer.progress) {
                    activeTransfers[transfer.transfer_id] = transfer;
                    updateTransferUI(transfer);

                    if (transfer.status === 'completed' && (!existing || existing.status !== 'completed')) {
                        showTransferNotification(transfer, 'completed');
                    } else if (transfer.status === 'failed' && (!existing || existing.status !== 'failed')) {
                        showTransferNotification(transfer, 'failed');
                    }
                }
            });

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

    const bar = document.querySelector(`.file-item[data-transfer-id="${transfer.transfer_id}"] .file-progress-bar`);
    if (bar) {
        bar.style.width = `${Math.round(transfer.progress || 0)}%`;
        if (transfer.status === 'completed') {
            bar.style.background = 'linear-gradient(90deg, #4CAF50, #4CAF50)';
        } else if (transfer.status === 'failed') {
            bar.style.background = 'linear-gradient(90deg, #f44336, #f44336)';
        }
    }

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

startTransfersPolling();

fetchPeersPolling();
setInterval(fetchPeersPolling, 1000);

function selectPeer(peerId) {
    const peer = peers.find(p => p.id === peerId);
    if (!peer) return;

    activePeer = peer;

    const cached = loadMessagesFromStorage(peer.username);
    if (cached) {
        messages[peer.username] = cached;
    } else {
        messages[peer.username] = messages[peer.username] || [];
    }

    if (!peer.has_chat) {
        fetch('/api/start_chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ peer: peer.username })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                console.log('Chat started with', peer.username);
                peer.has_chat = true;
            }
        })
        .catch(err => console.error('Failed to start chat:', err));
    }

    renderMessages();
    renderPeers();
    updateHeader();
    startMessagePolling();
}

function renderPeers(filter = '') {
    const filtered = peers.filter(p => 
        (p.username || '').toLowerCase().includes(filter.toLowerCase())
    );

    peersList.classList.add('updating');

    requestAnimationFrame(() => {
        const newHTML = filtered.map(peer => `
            <div class="peer-item ${activePeer && activePeer.id === peer.id ? 'active' : ''}" 
                 data-peer-id="${peer.id}">
                <div class="avatar" style="background: var(--color-bg-${(peer.username.charCodeAt(0) % 8) + 1});">
                    ${getInitials(peer.username)}
                </div>
                <div class="peer-info">
                    <div class="peer-name">${peer.username}</div>
                    <div class="peer-meta">
                        <span class="peer-ping">
                            <span class="ping-dot ${peer.online ? 'online' : 'offline'}"></span>
                            ${peer.ping}ms
                        </span>
                    </div>
                </div>
            </div>
        `).join('');

        if (peersList.innerHTML !== newHTML) {
            peersList.innerHTML = newHTML;
        }

        peersList.classList.remove('updating');

        document.querySelectorAll('.peer-item').forEach(item => {
            item.addEventListener('click', () => {
                const peerId = item.dataset.peerId;
                selectPeer(peerId);
            });
        });
    });
}

function renderMessages() {
    if (!activePeer) {
        messagesArea.innerHTML = `
            <div class="empty-state">
                <svg width="100" height="100" viewBox="0 0 100 100" fill="currentColor">
                    <path d="M50 10c-22.1 0-40 17.9-40 40s17.9 40 40 40 40-17.9 40-40-17.9-40-40-40zm0 75c-19.3 0-35-15.7-35-35s15.7-35 35-35 35 15.7 35 35-15.7 35-35 35z"/>
                    <circle cx="37" cy="42" r="4"/>
                    <circle cx="63" cy="42" r="4"/>
                    <path d="M50 70c-8.8 0-16-7.2-16-16h5c0 6.1 4.9 11 11 11s11-4.9 11-11h5c0 8.8-7.2 16-16 16z"/>
                </svg>
                <p>Выберите контакт для начала общения</p>
            </div>
        `;
        return;
    }

    const msgs = messages[activePeer.username] || [];

    if (msgs.length === 0) {
        messagesArea.innerHTML = `
            <div class="empty-state">
                <svg width="100" height="100" viewBox="0 0 100 100" fill="currentColor">
                    <path d="M50 20c-16.5 0-30 13.5-30 30s13.5 30 30 30 30-13.5 30-30-13.5-30-30-30zm0 55c-13.8 0-25-11.2-25-25s11.2-25 25-25 25 11.2 25 25-11.2 25-25 25z"/>
                    <path d="M35 45h30v5H35z"/>
                </svg>
                <p>Нет сообщений. Начните диалог!</p>
            </div>
        `;
        return;
    }

    messagesArea.classList.add('updating');

    requestAnimationFrame(() => {
        const newHTML = msgs.map(msg => {
            const from = msg.sent ? currentUsername : (msg.from || activePeer.username);

            const timeStr = (() => {
                try {
                    return new Date(msg.time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
                } catch {
                    return msg.time || '';
                }
            })();

            const bubbleContent = (() => {
                const text = msg.text || '';
                const urlMatch = text.match(/(https?:\/\/\S+|\/uploads\/\S+|\/downloads\/\S+)/);
                if (urlMatch) {
                    const url = urlMatch[0];
                    if (isImageUrl(url)) {
                        return `<img src="${url}" class="msg-image"
                                     onclick="window.open('${url}','_blank')"
                                     onerror="this.style.display='none'">`;
                    }
                    const rest = text.replace(url, '').trim();
                    const filename = url.split('/').pop();
                    return `<a href="${url}" target="_blank">📎 ${filename}</a>${rest ? ' ' + escapeHtml(rest) : ''}`;
                }
                return escapeHtml(text);
            })();

            return `
                <div class="message ${msg.system ? 'system' : (msg.sent ? 'sent' : 'received')}">
                    ${!msg.sent && !msg.system ? `
                        <div class="message-avatar"><span>${getInitials(from)}</span></div>
                    ` : ''}
                    <div class="message-content">
                        <div class="message-bubble">
                            ${bubbleContent}
                            <span class="message-time">
                                ${timeStr}${msg.status === 'sending' ? ' (отправка...)' : ''}
                            </span>
                        </div>
                    </div>
                    ${msg.sent && !msg.system ? `
                        <div class="message-avatar"><span>${getInitials(from)}</span></div>
                    ` : ''}
                </div>
            `;
        }).join('');

        if (messagesArea.innerHTML !== newHTML) {
            messagesArea.innerHTML = newHTML;
            messagesArea.scrollTo({ top: messagesArea.scrollHeight, behavior: 'smooth' });
        }

        setTimeout(() => messagesArea.classList.remove('updating'), 100);
    });
}

function updateHeader() {
    if (currentUserName) {
        currentUserName.textContent = currentUsername;
    }

    if (activePeer) {
        messageInputWrapper.style.display = 'flex';
        headerName.textContent = activePeer.username;
        headerStatus.textContent = activePeer.online ? 'Онлайн' : 'Офлайн';
    } else {
        messageInputWrapper.style.display = 'none';
        headerName.textContent = 'Выберите чат';
        headerStatus.textContent = 'Выберите контакт для начала общения';
    }
}

async function sendMessage() {
    if (!activePeer || (!messageInput.value.trim() && selectedFiles.length === 0)) return;

    const text = messageInput.value.trim();
    const now = new Date();
    const time = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    const localId = `local_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    if (text) {
        messages[activePeer.username] = messages[activePeer.username] || [];
        messages[activePeer.username].push({
            id: localId,
            text,
            time,
            sent: true,
            from: currentUsername,
            status: 'sending'
        });
        messageInput.value = '';
        renderMessages();
    }

    if (selectedFiles.length > 0) {
        messages[activePeer.username] = messages[activePeer.username] || [];
        selectedFiles.forEach(item => {
            messages[activePeer.username].push({
                text: `📎 ${item.file.name}`,
                time,
                sent: true,
                from: currentUsername
            });
        });
        renderMessages();
    }

    if (text) {
        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ peer: activePeer.username, text })
            });

            const result = await response.json();

            const ok = result.success || result.status === 'sent';

            if (ok) {
                const msgList = messages[activePeer.username];
                if (msgList) {
                    for (let i = msgList.length - 1; i >= 0; i--) {
                        const msg = msgList[i];
                        if (msg.id === localId || (msg.text === text && msg.status === 'sending')) {
                            msg.id = result.msg_id || result.timestamp
                                ? `sent_${result.msg_id || result.timestamp}`
                                : msg.id;
                            msg.status = 'sent';
                            break;
                        }
                    }
                }
                saveMessagesToStorage(activePeer.username);
                renderMessages();

                setTimeout(() => {
                    if (activePeer && messagesPollInterval) {
                        clearInterval(messagesPollInterval);
                        startMessagePolling();
                    }
                }, 500);
            } else {
                notifications.error(`Ошибка отправки: ${result.error || 'неизвестная ошибка'}`);
            }
        } catch (err) {
            console.error('Send error:', err);
            notifications.error('Ошибка при отправке сообщения');
        }
    }

    if (selectedFiles.length > 0) {
        const filesToUpload = selectedFiles.slice();

        for (const { file, uid } of filesToUpload) {
            try {
                const res = await uploadFileInChunks(file, activePeer.username, (p) => {
                    const bar = document.querySelector(`.file-item[data-uid="${uid}"] .file-progress-bar`);
                    if (bar) bar.style.width = `${Math.round(p * 100)}%`;
                });

                if (res?.upload_id) {
                    try {
                        const sendRes = await fetch('/api/send_uploaded_file', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ upload_id: res.upload_id, peer: activePeer.username })
                        });

                        if (sendRes.ok) {
                            const sendData = await sendRes.json();

                            if (sendData.transfer_id) {
                                activeTransfers[sendData.transfer_id] = {
                                    transfer_id: sendData.transfer_id,
                                    filename: file.name,
                                    status: 'pending',
                                    progress: 0,
                                    direction: 'upload'
                                };
                                const fileItem = document.querySelector(`.file-item[data-uid="${uid}"]`);
                                if (fileItem) {
                                    fileItem.dataset.transferId = sendData.transfer_id;
                                    const statusDiv = document.createElement('div');
                                    statusDiv.className = 'file-status';
                                    statusDiv.textContent = 'Ожидание...';
                                    fileItem.appendChild(statusDiv);
                                }
                            } else if (res.file_url) {
                                await fetch('/api/send_message', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        peer: activePeer.username,
                                        text: `📎 ${file.name} ${res.file_url}`
                                    })
                                }).catch(() => {});
                            }
                        } else {
                            throw new Error('P2P send failed');
                        }
                    } catch (err) {
                        console.warn('P2P fallback to link:', err);
                        if (res.file_url) {
                            await fetch('/api/send_message', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    peer: activePeer.username,
                                    text: `📎 ${file.name} ${res.file_url}`
                                })
                            }).catch(() => {});
                        }
                    }
                }
            } catch (err) {
                console.error('Upload failed:', err);
                const bar = document.querySelector(`.file-item[data-uid="${uid}"] .file-progress-bar`);
                if (bar) bar.style.background = 'linear-gradient(90deg, var(--color-error), var(--color-error))';
            }
        }

        selectedFiles = [];
        renderFilePreview();
    }
}

async function uploadFile(file, uid) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('peer', activePeer.username);

    const progressBar = document.querySelector(`[data-file-uid="${uid}"] .file-progress-bar`);

    try {
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && progressBar) {
                const pct = (e.loaded / e.total) * 100;
                progressBar.style.width = pct + '%';
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                try {
                    const result = JSON.parse(xhr.responseText);
                    if (result.success) {
                        notifications.success(`Файл "${file.name}" отправлен`);
                    } else {
                        notifications.error(`Ошибка: ${result.error}`);
                    }
                } catch (e) {
                    notifications.error('Ошибка парсинга ответа');
                }
            } else {
                notifications.error('Ошибка загрузки файла');
            }
        });

        xhr.addEventListener('error', () => {
            notifications.error(`Не удалось загрузить "${file.name}"`);
        });

        xhr.open('POST', '/api/send_file');
        xhr.send(formData);
    } catch (err) {
        console.error('Upload error:', err);
        notifications.error(`Ошибка загрузки "${file.name}"`);
    }
}

function renderFilePreview() {
    if (selectedFiles.length === 0) {
        filePreview.classList.add('hidden');
        filePreview.innerHTML = '';
        return;
    }

    filePreview.classList.remove('hidden');

    const html = selectedFiles.map(({file, uid}) => `
        <div class="file-item" data-file-uid="${uid}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
            <span>${file.name}</span>
            <div class="file-progress">
                <div class="file-progress-bar"></div>
            </div>
            <button class="file-remove" data-file-uid="${uid}">×</button>
        </div>
    `).join('');

    filePreview.innerHTML = html;

    document.querySelectorAll('.file-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            const uid = btn.dataset.fileUid;
            selectedFiles = selectedFiles.filter(f => f.uid !== uid);
            renderFilePreview();
        });
    });
}

function changeUsername() {
    const newUsername = prompt('Введите новое имя пользователя:', currentUsername);

    if (newUsername && newUsername.trim() && newUsername !== currentUsername) {
        const username = newUsername.trim();

        if (username.length > 20) {
            notifications.error('Имя слишком длинное (максимум 20 символов)');
            return;
        }

        if (!/^[A-Za-zА-Яа-я0-9_]+$/.test(username)) {
            notifications.error('Имя может содержать только буквы, цифры и подчеркивания');
            return;
        }

        fetch('/api/set_username', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                currentUsername = username;
                localStorage.setItem('messenger_username', username);
                notifications.success(`Имя изменено на: ${username}`);

                fetch('/api/refresh_peers', { method: 'POST' })
                    .then(() => console.log('Broadcast sent after username change'))
                    .catch(e => console.log('Failed to refresh peers:', e));

                updateHeader();
            } else {
                notifications.error(`Ошибка: ${result.error}`);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            notifications.error('Произошла ошибка. Попробуйте снова.');
        });
    }
}

sendBtn.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

searchInput.addEventListener('input', (e) => {
    renderPeers(e.target.value);
});

attachBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', (e) => {
    const files = Array.from(e.target.files);
    files.forEach(file => {
        const uid = Math.random().toString(36).substr(2, 9);
        selectedFiles.push({ file, uid });
    });
    renderFilePreview();
    fileInput.value = '';
});

document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'u') {
        e.preventDefault();
        changeUsername();
    }
});

updateHeader();
renderPeers();
renderMessages();
