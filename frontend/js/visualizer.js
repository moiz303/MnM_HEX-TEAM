// Глобальные функции для визуализатора

// Глобальные функции
window.updateVisualizerStats = updateVisualizerStats;
window.toggleAnimation = toggleAnimation;
window.sendTestMessage = sendTestMessage;
window.clearVisualizerLogs = clearVisualizerLogs;

class MeshVisualizer {
    constructor() {
        this.canvas = document.getElementById('network-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.nodes = new Map();
        this.connections = [];
        this.animationRunning = false;
        this.animationFrame = 0;
        
        this.setupCanvas();
        this.setupEventListeners();
        this.addLog('Mesh Network Visualizer инициализирован', 'success');
    }
    
    setupCanvas() {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        window.addEventListener('resize', () => {
            const rect = this.canvas.getBoundingClientRect();
            this.canvas.width = rect.width;
            this.canvas.height = rect.height;
            this.draw();
        });
    }
    
    setupEventListeners() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            this.handleMouseMove(x, y, e.clientX, e.clientY);
        });
        
        this.canvas.addEventListener('mouseleave', () => {
            const nodeInfo = document.getElementById('node-info');
            if (nodeInfo) {
                nodeInfo.style.display = 'none';
            }
        });
    }
    
    handleMouseMove(x, y, clientX, clientY) {
        const nodeInfo = document.getElementById('node-info');
        if (!nodeInfo) return;
        
        let hoveredNode = null;
        
        for (const [id, node] of this.nodes) {
            const dist = Math.sqrt(Math.pow(x - node.x, 2) + Math.pow(y - node.y, 2));
            if (dist < 20) {
                hoveredNode = node;
                break;
            }
        }
        
        if (hoveredNode) {
            nodeInfo.innerHTML = `
                <strong>${hoveredNode.name}</strong><br>
                ID: ${hoveredNode.id}<br>
                Статус: ${hoveredNode.online ? '🟢 Онлайн' : '🔴 Офлайн'}<br>
                Ретранслятор: ${hoveredNode.isRelay ? 'Да' : 'Нет'}<br>
                Нагрузка: ${hoveredNode.load}%
            `;
            nodeInfo.style.display = 'block';
            nodeInfo.style.left = clientX + 10 + 'px';
            nodeInfo.style.top = clientY + 10 + 'px';
        } else {
            nodeInfo.style.display = 'none';
        }
    }
    
    addNode(id, name, isRelay = false, load = 0, online = true) {
        const angle = Math.random() * Math.PI * 2;
        const radius = Math.min(this.canvas.width, this.canvas.height) * 0.3;
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        
        this.nodes.set(id, {
            id,
            name,
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius,
            isRelay,
            load,
            online,
            color: this.getNodeColor(isRelay, online),
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5
        });
        
        this.addLog(`Узел ${name} добавлен в сеть`, 'info');
    }
    
    getNodeColor(isRelay, online) {
        if (!online) return '#666666'; // Офлайн - серый
        if (isRelay) return '#00d9ff'; // Ретранслятор - голубой
        return '#4CAF50'; // Обычный узел - зеленый
    }
    
    addConnection(fromId, toId, strength = 1.0) {
        this.connections.push({
            from: fromId,
            to: toId,
            strength,
            active: true
        });
    }
    
    draw() {
        if (!this.ctx) return;
        
        // Очистка canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Отрисовка соединений
        this.connections.forEach(conn => {
            const fromNode = this.nodes.get(conn.from);
            const toNode = this.nodes.get(conn.to);
            
            if (fromNode && toNode) {
                this.ctx.beginPath();
                this.ctx.moveTo(fromNode.x, fromNode.y);
                this.ctx.lineTo(toNode.x, toNode.y);
                this.ctx.strokeStyle = `rgba(255, 255, 255, ${conn.strength * 0.3})`;
                this.ctx.lineWidth = conn.strength * 2;
                this.ctx.stroke();
            }
        });
        
        // Отрисовка узлов
        this.nodes.forEach(node => {
            // Анимация для онлайн узлов
            let radius = 15;
            if (node.online && this.animationRunning) {
                radius += Math.sin(this.animationFrame * 0.05 + parseFloat(node.id)) * 3;
            }
            
            // Тень
            this.ctx.shadowColor = node.color;
            this.ctx.shadowBlur = node.online ? 10 : 0;
            
            // Круг узла
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = node.color;
            this.ctx.fill();
            this.ctx.strokeStyle = 'white';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
            
            // Сброс тени
            this.ctx.shadowBlur = 0;
            
            // Имя узла
            this.ctx.fillStyle = 'white';
            this.ctx.font = '12px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(node.name, node.x, node.y - 25);
            
            // Статус
            this.ctx.font = '10px Arial';
            this.ctx.fillText(node.online ? '🟢' : '🔴', node.x + 20, node.y - 20);
        });
    }
    
    animate() {
        if (!this.animationRunning) return;
        
        this.animationFrame++;
        
        // Обновление позиций узлов (слегка двигаются)
        this.nodes.forEach(node => {
            node.x += node.vx;
            node.y += node.vy;
            
            // Отталкивание от границ
            if (node.x < 20 || node.x > this.canvas.width - 20) node.vx *= -1;
            if (node.y < 20 || node.y > this.canvas.height - 20) node.vy *= -1;
        });
        
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
    
    async fetchStats() {
        try {
            const response = await fetch('/api/peers');
            const data = await response.json();
            
            this.updateStats(data);
            this.updateNodes(data);
            
            return data;
        } catch (error) {
            this.addLog('Ошибка получения статистики: ' + error.message, 'error');
        }
    }
    
    updateStats(data) {
        // Обновление счетчиков
        const nodeCount = document.getElementById('node-count');
        const relayCount = document.getElementById('relay-count');
        const messageCount = document.getElementById('message-count');
        const circuitCount = document.getElementById('circuit-count');
        
        if (nodeCount) nodeCount.textContent = data.peers ? data.peers.length : 0;
        if (relayCount) relayCount.textContent = data.known_relays || 0;
        if (messageCount) messageCount.textContent = data.queued_messages || 0;
        if (circuitCount) circuitCount.textContent = data.active_circuits || 0;
    }
    
    updateNodes(data) {
        // Очистка существующих узлов
        this.nodes.clear();
        this.connections = [];
        
        // Добавление текущего пользователя
        if (data.device_id) {
            const username = localStorage.getItem('messenger_username') || 'Вы';
            this.addNode(data.device_id, username, true, 0, true);
        }
        
        // Добавление пиров из сети
        if (data.peers && data.peers.length > 0) {
            data.peers.forEach((peer, index) => {
                const isRelay = peer.is_relay || false;
                const load = Math.random() * 100; // Симуляция нагрузки
                this.addNode(peer.device_id || `peer_${index}`, peer.username, isRelay, load, true);
                
                // Создание соединений с текущим пользователем
                if (data.device_id) {
                    this.addConnection(data.device_id, peer.device_id || `peer_${index}`, 0.8);
                }
            });
        }
        
        // Добавление исторических пиров (офлайн)
        const historicalPeers = this.getHistoricalPeers();
        historicalPeers.forEach(peer => {
            // Проверяем, что этого пира нет в онлайн списке
            if (!data.peers || !data.peers.find(p => p.username === peer.username)) {
                this.addNode(peer.device_id || `hist_${peer.username}`, peer.username, false, 0, false);
            }
        });
        
        this.draw();
    }
    
    getHistoricalPeers() {
        const historical = localStorage.getItem('historical_peers');
        return historical ? JSON.parse(historical) : [];
    }
    
    addLog(message, type = 'info') {
        const logContent = document.getElementById('log-content');
        if (!logContent) return;
        
        const timestamp = new Date().toLocaleTimeString();
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
        
        logContent.insertBefore(entry, logContent.firstChild);
        
        // Ограничить количество записей
        while (logContent.children.length > 50) {
            logContent.removeChild(logContent.lastChild);
        }
    }
    
    startPolling() {
        this.fetchStats();
        this.pollingInterval = setInterval(() => this.fetchStats(), 5000);
        this.addLog('Начато автоматическое обновление (каждые 5 сек)', 'info');
    }
    
    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            this.addLog('Автоматическое обновление остановлено', 'info');
        }
    }
}

// Глобальные функции
function updateVisualizerStats() {
    if (visualizer) {
        visualizer.fetchStats();
        visualizer.addLog('Статистика обновлена вручную', 'success');
    }
}

function toggleAnimation() {
    if (visualizer) {
        visualizer.animationRunning = !visualizer.animationRunning;
        if (visualizer.animationRunning) {
            visualizer.animate();
            visualizer.addLog('Анимация включена', 'info');
        } else {
            visualizer.addLog('Анимация выключена', 'info');
        }
    }
}

function sendTestMessage() {
    if (visualizer) {
        visualizer.addLog('Отправка тестового сообщения через mesh-сеть...', 'info');
        
        // Симуляция отправки сообщения
        setTimeout(() => {
            visualizer.addLog('Тестовое сообщение успешно доставлено', 'success');
        }, 1000);
    }
}

function clearVisualizerLogs() {
    const logContent = document.getElementById('log-content');
    if (logContent) {
        logContent.innerHTML = '';
        if (visualizer) {
            visualizer.addLog('Логи очищены', 'info');
        }
    }
}

// Объявление глобальной переменной
let visualizer;

// Инициализация визуализатора при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Инициализация только если на странице визуализатора
    if (document.getElementById('network-canvas')) {
        visualizer = new MeshVisualizer();
        
        // Проверяем наличие API перед запуском
        fetch('/api/mesh/stats')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    visualizer.addLog('Визуализатор недоступен - messenger не инициализирован', 'error');
                    visualizer.addLog('Пожалуйста, войдите в систему', 'warning');
                } else {
                    visualizer.addLog('Mesh Network Visualizer готов к работе', 'success');
                    visualizer.startPolling();
                }
            })
            .catch(error => {
                visualizer.addLog('Ошибка подключения к API', 'error');
            });
    }
});

// Остановка опроса при уходе со страницы
document.addEventListener('visibilitychange', () => {
    if (document.hidden && visualizer) {
        visualizer.stopPolling();
    } else if (!document.hidden && visualizer && currentPage === 'visualizer') {
        visualizer.startPolling();
    }
});
