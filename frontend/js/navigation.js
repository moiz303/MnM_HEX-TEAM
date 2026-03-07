// Навигация между страницами
let currentPage = 'chat';
let currentUser = null;

// Показать страницу
function showPage(pageName) {
    // Проверка авторизации для всех страниц кроме входа
    if (pageName !== 'login' && !isAuthenticated()) {
        showNotification('Сначала войдите в систему', 'warning');
        showPage('login');
        return;
    }
    
    // Скрыть все страницы
    document.querySelectorAll('.page-container').forEach(page => {
        page.classList.remove('active');
    });
    
    // Убрать активный класс со всех кнопок
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Показать выбранную страницу
    const targetPage = document.getElementById(`${pageName}-page`);
    if (targetPage) {
        targetPage.classList.add('active');
    }
    
    // Активировать кнопку навигации
    const navBtn = document.getElementById(`nav-${pageName}`);
    if (navBtn) {
        navBtn.classList.add('active');
    }
    
    currentPage = pageName;
    
    // Инициализация страницы
    initializePage(pageName);
}

// Проверка авторизации
function isAuthenticated() {
    const username = localStorage.getItem('messenger_username');
    return username && username.trim() !== '';
}

// Навигация с проверкой авторизации
function navigateIfAuth(pageName) {
    if (isAuthenticated()) {
        showPage(pageName);
    } else {
        showNotification('Сначала войдите в систему', 'warning');
        showPage('login');
    }
}

// Инициализация страницы
function initializePage(pageName) {
    switch(pageName) {
        case 'chat':
            initializeChat();
            break;
        case 'visualizer':
            initializeVisualizer();
            break;
        case 'dashboard':
            initializeDashboard();
            break;
        case 'login':
            initializeLogin();
            break;
    }
}

// Инициализация чата
function initializeChat() {
    updateUserInfo();
    loadPeers();
    
    // Запускаем периодическое обновление пиров
    if (!window.peersInterval) {
        window.peersInterval = setInterval(() => {
            if (currentPage === 'chat' && isAuthenticated()) {
                loadPeers();
            }
        }, 5000);
    }
}

// Инициализация визуализатора
function initializeVisualizer() {
    if (window.visualizer) {
        window.visualizer.startPolling();
        window.visualizer.addLog('Переключение на страницу визуализатора', 'info');
    } else {
        showNotification('Визуализатор не инициализирован', 'error');
    }
}

// Инициализация дашборда
function initializeDashboard() {
    updateTestResults();
    addTestLog('Дашборд загружен', 'info');
}

// Инициализация входа
function initializeLogin() {
    // Фокус на поле ввода имени
    const usernameInput = document.getElementById('username-input');
    if (usernameInput) {
        usernameInput.focus();
    }
}

// Выход из системы
function logout() {
    localStorage.removeItem('messenger_username');
    currentUser = null;
    
    // Очищаем интервалы
    if (window.peersInterval) {
        clearInterval(window.peersInterval);
        window.peersInterval = null;
    }
    
    showNotification('Вы вышли из системы', 'info');
    showPage('login');
}

// Обновление информации о пользователе
function updateUserInfo() {
    const navUser = document.getElementById('nav-user');
    const currentUserName = document.getElementById('current-user-name');
    
    // Получаем имя пользователя из localStorage или API
    const username = localStorage.getItem('messenger_username') || 'Гость';
    
    if (navUser) {
        if (isAuthenticated()) {
            navUser.innerHTML = `👤 ${username} <button onclick="logout()" style="margin-left: 10px; padding: 2px 8px; background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); border-radius: 10px; color: white; cursor: pointer;">Выйти</button>`;
        } else {
            navUser.textContent = '👤 Гость';
        }
    }
    
    if (currentUserName) {
        currentUserName.textContent = username;
    }
    
    currentUser = username;
}

// Загрузка списка пиров с указанием статуса
async function loadPeers() {
    try {
        // Получаем текущих пиров
        const response = await fetch('/api/peers');
        const data = await response.json();
        
        const peersList = document.getElementById('peers-list');
        if (!peersList) return;
        
        peersList.innerHTML = '';
        
        if (data.peers && data.peers.length > 0) {
            // Добавляем онлайн пиров
            data.peers.forEach(peer => {
                const peerElement = createPeerElement(peer, true);
                peersList.appendChild(peerElement);
            });
        }
        
        // Добавляем исторических пиров (офлайн)
        const historicalPeers = getHistoricalPeers();
        historicalPeers.forEach(peer => {
            // Проверяем, что этого пира нет в онлайн списке
            if (!data.peers || !data.peers.find(p => p.username === peer.username)) {
                const peerElement = createPeerElement(peer, false);
                peersList.appendChild(peerElement);
            }
        });
        
        if (peersList.children.length === 0) {
            peersList.innerHTML = '<div class="no-peers">Нет доступных пиров</div>';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки пиров:', error);
        const peersList = document.getElementById('peers-list');
        if (peersList) {
            peersList.innerHTML = '<div class="no-peers">Ошибка загрузки пиров</div>';
        }
    }
}

// Создание элемента пира со статусом
function createPeerElement(peer, isOnline) {
    const peerDiv = document.createElement('div');
    peerDiv.className = `peer-item ${isOnline ? 'online' : 'offline'}`;
    peerDiv.onclick = () => selectPeer(peer);
    
    const statusClass = isOnline ? 'online' : 'offline';
    const statusText = isOnline ? '🟢 Онлайн' : '🔴 Офлайн';
    
    peerDiv.innerHTML = `
        <div class="peer-avatar">
            <span class="avatar-text">${peer.username ? peer.username[0].toUpperCase() : '?'}</span>
        </div>
        <div class="peer-info">
            <div class="peer-name">${peer.username || 'Unknown'}</div>
            <div class="peer-status ${statusClass}">${statusText}</div>
        </div>
        <div class="peer-details">
            ${peer.ip ? `<div class="peer-ip">${peer.ip}</div>` : ''}
            ${peer.last_seen ? `<div class="peer-last-seen">Был в сети: ${formatLastSeen(peer.last_seen)}</div>` : ''}
        </div>
    `;
    
    return peerDiv;
}

// Получение исторических пиров
function getHistoricalPeers() {
    const historical = localStorage.getItem('historical_peers');
    return historical ? JSON.parse(historical) : [];
}

// Добавление пира в историю
function addToHistory(peer) {
    const historical = getHistoricalPeers();
    
    // Проверяем, есть ли уже такой пир в истории
    const existingIndex = historical.findIndex(p => p.username === peer.username);
    
    if (existingIndex >= 0) {
        // Обновляем существующего пира
        historical[existingIndex] = {
            ...peer,
            last_seen: new Date().toISOString()
        };
    } else {
        // Добавляем нового пира
        historical.push({
            ...peer,
            last_seen: new Date().toISOString()
        });
    }
    
    // Ограничиваем историю 50 пира
    if (historical.length > 50) {
        historical.splice(0, historical.length - 50);
    }
    
    localStorage.setItem('historical_peers', JSON.stringify(historical));
}

// Форматирование времени последнего появления
function formatLastSeen(lastSeen) {
    const date = new Date(lastSeen);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) {
        return 'только что';
    } else if (diff < 3600000) {
        return `${Math.floor(diff / 60000)} мин назад`;
    } else if (diff < 86400000) {
        return `${Math.floor(diff / 3600000)} ч назад`;
    } else {
        return date.toLocaleDateString();
    }
}

// Выбор пира для чата
function selectPeer(peer) {
    if (!peer || !peer.username) return;
    
    // Обновляем заголовок чата
    const headerName = document.getElementById('header-name');
    const headerStatus = document.getElementById('header-status');
    const headerStatusIndicator = document.getElementById('header-status-indicator');
    
    if (headerName) headerName.textContent = peer.username;
    if (headerStatus) headerStatus.textContent = peer.ip || 'Нет IP';
    
    // Обновляем индикатор статуса
    if (headerStatusIndicator) {
        const statusDot = headerStatusIndicator.querySelector('.status-dot');
        if (statusDot) {
            statusDot.className = `status-dot ${peer.online ? 'online' : 'offline'}`;
        }
    }
    
    // Активируем ввод сообщений
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const fileButton = document.getElementById('file-button');
    const fileInput = document.getElementById('file-input');
    
    if (messageInput) {
        messageInput.disabled = false;
        messageInput.placeholder = `Сообщение для ${peer.username}...`;
    }
    if (sendButton) sendButton.disabled = false;
    if (fileButton) fileButton.disabled = false;
    if (fileInput) fileInput.disabled = false;
    
    // Загружаем сообщения с этим пиром
    loadMessages(peer.username);
    
    // Добавляем пира в историю
    addToHistory(peer);
    
    showNotification(`Открыт чат с ${peer.username}`, 'success');
}

// Загрузка сообщений
async function loadMessages(peerUsername) {
    try {
        const response = await fetch(`/api/get_messages?peer=${peerUsername}&limit=50`);
        const data = await response.json();
        
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;
        
        chatMessages.innerHTML = '';
        
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(message => {
                const messageElement = createMessageElement(message);
                chatMessages.appendChild(messageElement);
            });
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            chatMessages.innerHTML = '<div class="no-messages">Нет сообщений</div>';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
    }
}

// Создание элемента сообщения
function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.sender === currentUser ? 'sent' : 'received'}`;
    
    messageDiv.innerHTML = `
        <div class="message-content">${message.content}</div>
        <div class="message-time">${formatMessageTime(message.timestamp)}</div>
    `;
    
    return messageDiv;
}

// Форматирование времени сообщения
function formatMessageTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Показать уведомление
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    if (!container) return;
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    container.appendChild(notification);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // ВСЕГДА начинаем со страницы входа
    showPage('login');
    
    // Обновляем информацию о пользователе
    updateUserInfo();
});

// Обработка формы входа
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const usernameInput = document.getElementById('username-input');
            const portInput = document.getElementById('port-input');
            
            const username = usernameInput.value.trim();
            const port = portInput.value || '8080';
            
            if (!username) {
                showNotification('Введите имя пользователя', 'error');
                return;
            }
            
            try {
                // Устанавливаем имя пользователя
                const response = await fetch('/api/set_username', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    // Сохраняем имя пользователя
                    localStorage.setItem('messenger_username', username);
                    currentUser = username;
                    
                    showNotification(`Добро пожаловать, ${username}!`, 'success');
                    
                    // Обновляем информацию о пользователе
                    updateUserInfo();
                    
                    // Переходим на страницу чатов
                    setTimeout(() => showPage('chat'), 1000);
                } else {
                    showNotification(data.error || 'Ошибка входа', 'error');
                }
                
            } catch (error) {
                console.error('Ошибка входа:', error);
                showNotification('Ошибка соединения с сервером', 'error');
            }
        });
    }
});

// Обработка отправки сообщений
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    
    const sendMessage = async () => {
        const message = messageInput.value.trim();
        if (!message || !activePeer) return;
        
        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    peer: activePeer.username,
                    message: message
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                messageInput.value = '';
                loadMessages(activePeer.username);
                showNotification('Сообщение отправлено', 'success');
            } else {
                showNotification(data.error || 'Ошибка отправки', 'error');
            }
            
        } catch (error) {
            console.error('Ошибка отправки сообщения:', error);
            showNotification('Ошибка соединения', 'error');
        }
    };
    
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
    
    if (messageInput) {
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
});
