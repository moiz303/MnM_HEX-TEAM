/**
 * Mesh Network Visualization Component
 * Provides real-time visualization of the P2P network topology
 */

class MeshNetworkVisualization {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container ${containerId} not found`);
            return;
        }

        this.nodes = new Map();
        this.edges = new Map();
        this.selectedNode = null;
        this.hoveredNode = null;
        
        this.setupCanvas();
        this.setupEventListeners();
        this.startAnimation();
    }

    setupCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.container.clientWidth;
        this.canvas.height = 400;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '400px';
        this.canvas.style.border = '2px solid var(--color-border)';
        this.canvas.style.borderRadius = 'var(--radius-lg)';
        this.canvas.style.background = 'linear-gradient(135deg, rgba(59, 130, 246, 0.02), rgba(168, 85, 247, 0.02))';
        
        this.ctx = this.canvas.getContext('2d');
        this.container.appendChild(this.canvas);
        
        // Handle resize
        window.addEventListener('resize', () => {
            this.canvas.width = this.container.clientWidth;
            this.canvas.height = 400;
        });
    }

    setupEventListeners() {
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            this.hoveredNode = this.getNodeAtPosition(x, y);
            this.canvas.style.cursor = this.hoveredNode ? 'pointer' : 'default';
            
            if (this.hoveredNode) {
                this.showNodeTooltip(this.hoveredNode, e.clientX, e.clientY);
            } else {
                this.hideNodeTooltip();
            }
        });

        this.canvas.addEventListener('click', (e) => {
            if (this.hoveredNode) {
                this.selectNode(this.hoveredNode);
            }
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.hoveredNode = null;
            this.hideNodeTooltip();
        });
    }

    addNode(id, data) {
        const node = {
            id,
            x: Math.random() * (this.canvas.width - 100) + 50,
            y: Math.random() * (this.canvas.height - 100) + 50,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            radius: 25,
            ...data
        };
        
        this.nodes.set(id, node);
        return node;
    }

    removeNode(id) {
        this.nodes.delete(id);
        // Remove connected edges
        for (const [edgeId, edge] of this.edges) {
            if (edge.source === id || edge.target === id) {
                this.edges.delete(edgeId);
            }
        }
    }

    addEdge(sourceId, targetId, data = {}) {
        const edgeId = `${sourceId}-${targetId}`;
        const edge = {
            id: edgeId,
            source: sourceId,
            target: targetId,
            strength: data.strength || 1,
            ...data
        };
        
        this.edges.set(edgeId, edge);
        return edge;
    }

    updateNode(id, data) {
        const node = this.nodes.get(id);
        if (node) {
            Object.assign(node, data);
        }
    }

    getNodeAtPosition(x, y) {
        for (const [id, node] of this.nodes) {
            const dx = x - node.x;
            const dy = y - node.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance <= node.radius) {
                return node;
            }
        }
        return null;
    }

    selectNode(node) {
        this.selectedNode = node;
        this.onNodeSelected?.(node);
    }

    showNodeTooltip(node, x, y) {
        this.hideNodeTooltip();
        
        const tooltip = document.createElement('div');
        tooltip.className = 'node-tooltip';
        tooltip.style.cssText = `
            position: fixed;
            left: ${x + 10}px;
            top: ${y - 30}px;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-base);
            padding: var(--space-sm) var(--space-md);
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            font-size: var(--font-size-sm);
            max-width: 200px;
        `;
        
        tooltip.innerHTML = `
            <div style="font-weight: 600; color: var(--color-text);">${node.username || node.id}</div>
            <div style="color: var(--color-text-secondary); font-size: var(--font-size-xs);">${node.ip || 'Unknown IP'}</div>
            <div style="color: ${node.online ? 'var(--color-success)' : 'var(--color-error)'}; font-size: var(--font-size-xs);">${node.online ? 'Online' : 'Offline'}</div>
        `;
        
        document.body.appendChild(tooltip);
        this.currentTooltip = tooltip;
    }

    hideNodeTooltip() {
        if (this.currentTooltip) {
            document.body.removeChild(this.currentTooltip);
            this.currentTooltip = null;
        }
    }

    startAnimation() {
        const animate = () => {
            this.update();
            this.draw();
            requestAnimationFrame(animate);
        };
        animate();
    }

    update() {
        // Apply physics simulation for better layout
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        
        for (const [id, node] of this.nodes) {
            // Apply center gravity
            const dx = centerX - node.x;
            const dy = centerY - node.y;
            node.vx += dx * 0.001;
            node.vy += dy * 0.001;
            
            // Apply repulsion between nodes
            for (const [otherId, otherNode] of this.nodes) {
                if (id !== otherId) {
                    const dx = node.x - otherNode.x;
                    const dy = node.y - otherNode.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 100 && distance > 0) {
                        const force = 50 / (distance * distance);
                        node.vx += (dx / distance) * force;
                        node.vy += (dy / distance) * force;
                    }
                }
            }
            
            // Apply edge attraction
            for (const [edgeId, edge] of this.edges) {
                if (edge.source === id || edge.target === id) {
                    const otherNode = this.nodes.get(edge.source === id ? edge.target : edge.source);
                    if (otherNode) {
                        const dx = otherNode.x - node.x;
                        const dy = otherNode.y - node.y;
                        const distance = Math.sqrt(dx * dx + dy * dy);
                        
                        if (distance > 80) {
                            node.vx += dx * 0.001;
                            node.vy += dy * 0.001;
                        }
                    }
                }
            }
            
            // Apply damping
            node.vx *= 0.9;
            node.vy *= 0.9;
            
            // Update position
            node.x += node.vx;
            node.y += node.vy;
            
            // Keep within bounds
            node.x = Math.max(node.radius, Math.min(this.canvas.width - node.radius, node.x));
            node.y = Math.max(node.radius, Math.min(this.canvas.height - node.radius, node.y));
        }
    }

    draw() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Draw edges
        this.ctx.strokeStyle = 'rgba(59, 130, 246, 0.3)';
        this.ctx.lineWidth = 2;
        
        for (const [edgeId, edge] of this.edges) {
            const sourceNode = this.nodes.get(edge.source);
            const targetNode = this.nodes.get(edge.target);
            
            if (sourceNode && targetNode) {
                this.ctx.beginPath();
                this.ctx.moveTo(sourceNode.x, sourceNode.y);
                this.ctx.lineTo(targetNode.x, targetNode.y);
                this.ctx.stroke();
                
                // Draw data flow animation
                const progress = (Date.now() / 3000) % 1;
                const x = sourceNode.x + (targetNode.x - sourceNode.x) * progress;
                const y = sourceNode.y + (targetNode.y - sourceNode.y) * progress;
                
                this.ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
                this.ctx.beginPath();
                this.ctx.arc(x, y, 3, 0, Math.PI * 2);
                this.ctx.fill();
            }
        }
        
        // Draw nodes
        for (const [id, node] of this.nodes) {
            const isSelected = this.selectedNode === node;
            const isHovered = this.hoveredNode === node;
            
            // Draw node shadow
            if (isSelected || isHovered) {
                this.ctx.shadowColor = 'rgba(59, 130, 246, 0.4)';
                this.ctx.shadowBlur = 15;
            }
            
            // Draw node
            this.ctx.fillStyle = node.online ? 'rgba(34, 197, 94, 0.8)' : 'rgba(239, 68, 68, 0.8)';
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            this.ctx.fill();
            
            // Reset shadow
            this.ctx.shadowColor = 'transparent';
            this.ctx.shadowBlur = 0;
            
            // Draw selection ring
            if (isSelected) {
                this.ctx.strokeStyle = 'rgba(59, 130, 246, 0.8)';
                this.ctx.lineWidth = 3;
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, node.radius + 5, 0, Math.PI * 2);
                this.ctx.stroke();
            }
            
            // Draw hover ring
            if (isHovered && !isSelected) {
                this.ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, node.radius + 3, 0, Math.PI * 2);
                this.ctx.stroke();
            }
            
            // Draw node label
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = 'bold 12px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            
            const label = node.username || node.id.substring(0, 8);
            const maxWidth = node.radius * 1.8;
            
            // Truncate text if too long
            let displayText = label;
            if (this.ctx.measureText(displayText).width > maxWidth) {
                while (this.ctx.measureText(displayText + '...').width > maxWidth && displayText.length > 0) {
                    displayText = displayText.slice(0, -1);
                }
                displayText += '...';
            }
            
            this.ctx.fillText(displayText, node.x, node.y);
        }
    }

    updateFromPeers(peers) {
        // Clear existing nodes
        this.nodes.clear();
        this.edges.clear();
        
        // Add current user as central node
        const currentUser = this.addNode('current', {
            username: currentUsername || 'You',
            online: true,
            ip: '127.0.0.1',
            isCurrent: true
        });
        
        // Add peer nodes
        peers.forEach(peer => {
            this.addNode(peer.device_id || peer.username, {
                username: peer.username,
                ip: peer.ip,
                online: peer.status === 'online',
                hasChat: peer.has_chat
            });
            
            // Add edge from current user to peer
            this.addEdge('current', peer.device_id || peer.username, {
                strength: peer.status === 'online' ? 1 : 0.3
            });
        });
    }

    destroy() {
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
        this.hideNodeTooltip();
    }
}

// Export for use in main app
window.MeshNetworkVisualization = MeshNetworkVisualization;
