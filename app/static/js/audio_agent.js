/**
 * ARIA Executive AI Voice Agent - Full-Stack Client Orchestrator
 * Real-time WebSockets, Web Audio API Visualizer, Browser Speech STT & Neural Audio Playback
 */

class VoiceAgentClient {
    constructor() {
        this.socket = null;
        this.sessionId = 'exec-session-' + Math.random().toString(36).substring(2, 9);
        this.state = 'idle'; // idle | listening | thinking | speaking
        this.audioChunks = [];
        this.currentAudio = null;
        this.recognition = null;
        this.isRecording = false;

        // Visualizer Setup
        this.canvas = document.getElementById('visualizer-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.wavePhase = 0;

        this.initDOMElements();
        this.initSpeechRecognition();
        this.initWebSocket();
        this.initVisualizer();
        this.refreshAllData();
    }

    initDOMElements() {
        this.micBtn = document.getElementById('mic-toggle-btn');
        this.micIcon = document.getElementById('mic-icon');
        this.micPulse = document.getElementById('mic-pulse-ring');
        this.micHint = document.getElementById('mic-hint');
        this.stateBadge = document.getElementById('agent-state-badge');
        this.stateText = document.getElementById('agent-state-text');
        this.orbAmbient = document.getElementById('orb-ambient');
        this.transcriptFeed = document.getElementById('transcript-feed');
        this.textForm = document.getElementById('text-input-form');
        this.textInput = document.getElementById('user-text-input');
        this.connDot = document.getElementById('connection-dot');
        this.connStatus = document.getElementById('connection-status');

        // Latency labels
        this.llmLatency = document.getElementById('metric-llm');
        this.ttsLatency = document.getElementById('metric-tts');
        this.totalLatency = document.getElementById('metric-total');

        // Panels
        this.tasksList = document.getElementById('tasks-list');
        this.tasksCount = document.getElementById('tasks-count');
        this.calendarList = document.getElementById('calendar-list');
        this.calendarCount = document.getElementById('calendar-count');
        this.memoriesList = document.getElementById('memories-list');
        this.memoriesCount = document.getElementById('memories-count');
        this.ragDocsList = document.getElementById('rag-docs-list');
        this.ragDocsCount = document.getElementById('rag-docs-count');

        // Event Listeners
        this.micBtn.addEventListener('click', () => this.toggleMicrophone());
        this.textForm.addEventListener('submit', (e) => this.handleTextSubmit(e));
        document.getElementById('clear-transcript-btn').addEventListener('click', () => {
            this.transcriptFeed.innerHTML = '';
        });
    }

    // -----------------------------------------------------------------------
    // WebSocket Client Management
    // -----------------------------------------------------------------------

    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/agent?session_id=${this.sessionId}`;

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            this.connDot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
            this.connStatus.textContent = 'Connected';
            console.log('Connected to Agent WebSocket');
        };

        this.socket.onclose = () => {
            this.connDot.className = 'w-2 h-2 rounded-full bg-red-400';
            this.connStatus.textContent = 'Disconnected';
            console.warn('Agent WebSocket closed, reconnecting in 3s...');
            setTimeout(() => this.initWebSocket(), 3000);
        };

        this.socket.onerror = (err) => {
            console.error('WebSocket Error:', err);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleServerMessage(data);
            } catch (e) {
                console.error('Failed to parse WS frame:', e);
            }
        };
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'connection_established':
                console.log('Session ready:', data.session_id);
                break;

            case 'status':
                this.setAgentState(data.status, data.message);
                break;

            case 'tool_executed':
                this.renderToolExecutionBadges(data.tools);
                break;

            case 'state_sync':
                this.refreshAllData();
                break;

            case 'speech_text':
                this.appendMessage('assistant', data.text, data.mode);
                break;

            case 'audio_stream_start':
                this.audioChunks = [];
                break;

            case 'audio_chunk':
                this.audioChunks.push(data.data);
                break;

            case 'audio_stream_end':
                this.playAudioChunks();
                break;

            case 'latency_metrics':
                this.llmLatency.textContent = `${data.llm_latency_ms} ms`;
                this.ttsLatency.textContent = `${data.tts_latency_ms} ms`;
                this.totalLatency.textContent = `${data.total_latency_ms} ms`;
                break;
        }
    }

    // -----------------------------------------------------------------------
    // Speech Recognition (Web Speech API)
    // -----------------------------------------------------------------------

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            console.warn('Web Speech API is not supported in this browser. Fallback to typed input.');
            this.micHint.textContent = 'Speech not supported in browser. Use typing input.';
            return;
        }

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';

        this.recognition.onstart = () => {
            this.isRecording = true;
            this.setAgentState('listening', 'Listening to you...');
            this.micHint.textContent = 'Listening... Speak now';
        };

        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Recognized speech:', transcript);
            this.appendMessage('user', transcript);
            this.sendUserPrompt(transcript);
        };

        this.recognition.onerror = (event) => {
            console.warn('Speech recognition error:', event.error);
            this.stopRecording();
            this.setAgentState('idle', 'Ready');
        };

        this.recognition.onend = () => {
            this.stopRecording();
        };
    }

    toggleMicrophone() {
        // If agent is currently speaking, barge-in interrupt
        if (this.state === 'speaking') {
            this.stopAudioPlayback();
            this.socket.send(JSON.stringify({ type: 'interrupt' }));
        }

        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }

    startRecording() {
        if (!this.recognition) {
            alert('Speech Recognition is not available. Please type your command in the input box below.');
            return;
        }
        try {
            this.recognition.start();
        } catch (e) {
            console.warn('Recognition start exception:', e);
        }
    }

    stopRecording() {
        this.isRecording = false;
        if (this.recognition) {
            try { this.recognition.stop(); } catch (e) {}
        }
        this.micHint.textContent = 'Click to Speak or Type below';
    }

    // -----------------------------------------------------------------------
    // Prompt Dispatcher & Audio Playback
    // -----------------------------------------------------------------------

    handleTextSubmit(e) {
        e.preventDefault();
        const text = this.textInput.value.trim();
        if (!text) return;

        // Barge-in if audio playing
        if (this.state === 'speaking') {
            this.stopAudioPlayback();
            this.socket.send(JSON.stringify({ type: 'interrupt' }));
        }

        this.appendMessage('user', text);
        this.sendUserPrompt(text);
        this.textInput.value = '';
    }

    sendUserPrompt(text) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                type: 'text_message',
                message: text,
                session_id: this.sessionId
            }));
        } else {
            console.error('Socket not open');
        }
    }

    playAudioChunks() {
        if (this.audioChunks.length === 0) return;

        // Decode base64 chunks into audio Blob
        const byteCharacters = atob(this.audioChunks.join(''));
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'audio/mpeg' });
        const audioUrl = URL.createObjectURL(blob);

        this.stopAudioPlayback();
        this.currentAudio = new Audio(audioUrl);

        this.currentAudio.onplay = () => {
            this.setAgentState('speaking', 'Speaking response...');
        };

        this.currentAudio.onended = () => {
            this.setAgentState('idle', 'Ready & Listening');
            URL.revokeObjectURL(audioUrl);
        };

        this.currentAudio.onerror = (err) => {
            console.error('Audio playback error:', err);
            this.setAgentState('idle', 'Ready & Listening');
        };

        this.currentAudio.play().catch(e => {
            console.warn('Auto-play prevented or failed:', e);
            this.setAgentState('idle', 'Ready & Listening');
        });
    }

    stopAudioPlayback() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
    }

    // -----------------------------------------------------------------------
    // State & UI Helpers
    // -----------------------------------------------------------------------

    setAgentState(state, message) {
        this.state = state;
        this.stateText.textContent = message || state;

        // Remove old states
        this.orbAmbient.className = 'absolute w-72 h-72 rounded-full blur-3xl transition-all duration-700 pointer-events-none ';
        this.micPulse.className = 'absolute inset-0 rounded-full transition-transform duration-500 ';

        switch (state) {
            case 'listening':
                this.orbAmbient.classList.add('orb-state-listening');
                this.micPulse.classList.add('bg-emerald-500/40', 'animate-pulse-ring');
                this.stateBadge.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium tracking-wide uppercase bg-emerald-950/80 text-emerald-300 border border-emerald-500/30';
                break;
            case 'thinking':
                this.orbAmbient.classList.add('orb-state-thinking');
                this.micPulse.classList.add('bg-cyan-500/40', 'animate-pulse');
                this.stateBadge.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium tracking-wide uppercase bg-cyan-950/80 text-cyan-300 border border-cyan-500/30';
                break;
            case 'speaking':
                this.orbAmbient.classList.add('orb-state-speaking');
                this.micPulse.classList.add('bg-purple-500/40', 'animate-pulse-ring');
                this.stateBadge.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium tracking-wide uppercase bg-purple-950/80 text-purple-300 border border-purple-500/30';
                break;
            default: // idle
                this.orbAmbient.classList.add('orb-state-idle');
                this.stateBadge.className = 'inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium tracking-wide uppercase bg-indigo-950/80 text-indigo-300 border border-indigo-500/30';
                break;
        }
    }

    appendMessage(role, text, mode) {
        const item = document.createElement('div');
        item.className = 'flex items-start gap-3 bg-slate-900/60 p-3 rounded-xl border border-cardborder/50 animate-fade-in';

        const isUser = role === 'user';
        const iconBg = isUser ? 'bg-cyan-500/20 text-cyan-400' : 'bg-indigo-500/20 text-indigo-400';
        const iconName = isUser ? 'user' : 'bot';
        const senderName = isUser ? 'You' : 'Aria';
        const tag = isUser ? 'Voice/Input' : (mode === 'live' ? 'Gemini 2.5' : 'Simulation');

        item.innerHTML = `
            <div class="w-7 h-7 rounded-lg ${iconBg} flex items-center justify-center shrink-0 mt-0.5">
                <i data-lucide="${iconName}" class="w-4 h-4"></i>
            </div>
            <div class="flex-1">
                <div class="flex items-center gap-2">
                    <span class="font-medium text-xs ${isUser ? 'text-cyan-400' : 'text-indigo-400'}">${senderName}</span>
                    <span class="text-[10px] text-slate-500">${tag}</span>
                </div>
                <p class="text-slate-200 text-xs mt-1 leading-relaxed">${text}</p>
            </div>
        `;

        this.transcriptFeed.appendChild(item);
        this.transcriptFeed.scrollTop = this.transcriptFeed.scrollHeight;
        lucide.createIcons();
    }

    renderToolExecutionBadges(tools) {
        if (!tools || tools.length === 0) return;
        tools.forEach(t => {
            const badge = document.createElement('div');
            badge.className = 'flex items-center gap-2 bg-indigo-950/70 border border-indigo-500/30 text-indigo-300 px-3 py-1.5 rounded-lg text-xs my-1 font-mono';
            badge.innerHTML = `
                <i data-lucide="cog" class="w-3.5 h-3.5 text-indigo-400 animate-spin"></i>
                <span>Executed Tool: <strong>${t.tool || t.name}</strong></span>
            `;
            this.transcriptFeed.appendChild(badge);
        });
        this.transcriptFeed.scrollTop = this.transcriptFeed.scrollHeight;
        lucide.createIcons();
    }

    // -----------------------------------------------------------------------
    // Canvas Wave Visualizer Animation
    // -----------------------------------------------------------------------

    initVisualizer() {
        const render = () => {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            const width = this.canvas.width;
            const height = this.canvas.height;
            const centerY = height / 2;

            let amplitude = 8;
            let strokeColor = 'rgba(99, 102, 241, 0.4)';

            if (this.state === 'listening') {
                amplitude = 28;
                strokeColor = 'rgba(16, 185, 129, 0.9)';
            } else if (this.state === 'thinking') {
                amplitude = 18;
                strokeColor = 'rgba(6, 182, 212, 0.9)';
            } else if (this.state === 'speaking') {
                amplitude = 36;
                strokeColor = 'rgba(168, 85, 247, 0.9)';
            }

            // Draw primary harmonic wave
            this.ctx.beginPath();
            this.ctx.lineWidth = 2.5;
            this.ctx.strokeStyle = strokeColor;

            for (let x = 0; x < width; x++) {
                const angle = (x / width) * Math.PI * 4 + this.wavePhase;
                const y = centerY + Math.sin(angle) * amplitude * Math.sin(x / width * Math.PI);
                if (x === 0) this.ctx.moveTo(x, y);
                else this.ctx.lineTo(x, y);
            }
            this.ctx.stroke();

            // Draw secondary harmonic glow wave
            this.ctx.beginPath();
            this.ctx.lineWidth = 1;
            this.ctx.strokeStyle = strokeColor.replace('0.9', '0.35');

            for (let x = 0; x < width; x++) {
                const angle = (x / width) * Math.PI * 6 - this.wavePhase * 1.5;
                const y = centerY + Math.cos(angle) * (amplitude * 0.6) * Math.sin(x / width * Math.PI);
                if (x === 0) this.ctx.moveTo(x, y);
                else this.ctx.lineTo(x, y);
            }
            this.ctx.stroke();

            this.wavePhase += this.state === 'idle' ? 0.03 : 0.08;
            requestAnimationFrame(render);
        };

        requestAnimationFrame(render);
    }

    // -----------------------------------------------------------------------
    // Data Sync Operations (Tasks, Calendar, Memories)
    // -----------------------------------------------------------------------

    async refreshAllData() {
        await Promise.all([
            this.fetchTasks(),
            this.fetchCalendar(),
            this.fetchMemories(),
            this.fetchRagDocs()
        ]);
    }

    async fetchTasks() {
        try {
            const res = await fetch('/api/tasks?limit=10');
            const data = await res.json();
            this.tasksCount.textContent = `${data.count} Tasks`;

            if (data.tasks.length === 0) {
                this.tasksList.innerHTML = `<div class="text-center py-6 text-xs text-slate-500">No tasks on agenda.</div>`;
                return;
            }

            this.tasksList.innerHTML = data.tasks.map(t => {
                const isDone = t.status === 'completed';
                const priorityBadge = t.priority === 'urgent' 
                    ? 'bg-red-500/20 text-red-400 border-red-500/30'
                    : (t.priority === 'high' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : 'bg-slate-800 text-slate-400 border-slate-700');

                return `
                    <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-900/40 border border-cardborder hover:border-slate-700 transition-colors">
                        <div class="flex items-center gap-2.5 flex-1 min-w-0">
                            <input type="checkbox" ${isDone ? 'checked' : ''} onchange="agentApp.toggleTaskStatus(${t.id}, this.checked)"
                                class="rounded bg-slate-800 border-slate-700 text-emerald-500 focus:ring-0 cursor-pointer">
                            <div class="truncate">
                                <p class="text-xs font-medium text-slate-200 ${isDone ? 'line-through text-slate-500' : ''} truncate">${t.title}</p>
                                <p class="text-[10px] text-slate-500">${t.due_date ? `Due: ${t.due_date}` : 'No due date'}</p>
                            </div>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded-full border font-mono uppercase ${priorityBadge}">${t.priority}</span>
                    </div>
                `;
            }).join('');
        } catch (e) {
            console.error('Failed to fetch tasks:', e);
        }
    }

    async toggleTaskStatus(taskId, isChecked) {
        try {
            await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: isChecked ? 'completed' : 'pending' })
            });
            this.fetchTasks();
        } catch (e) {
            console.error('Failed to update task:', e);
        }
    }

    async fetchCalendar() {
        try {
            const res = await fetch('/api/calendar?status=scheduled&limit=8');
            const data = await res.json();
            this.calendarCount.textContent = `${data.count} Events`;

            if (data.events.length === 0) {
                this.calendarList.innerHTML = `<div class="text-center py-6 text-xs text-slate-500">No scheduled events found. Speak to schedule one.</div>`;
                return;
            }

            this.calendarList.innerHTML = data.events.map(e => `
                <div class="p-3 rounded-xl bg-slate-900/40 border border-cardborder hover:border-slate-700 transition-colors">
                    <div class="flex items-start justify-between">
                        <p class="text-xs font-semibold text-slate-100 truncate">${e.title}</p>
                        <span class="text-[10px] text-cyan-400 font-mono">${e.start_time}</span>
                    </div>
                    <div class="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400">
                        ${e.location ? `<span><i data-lucide="map-pin" class="w-3 h-3 inline mr-1 text-slate-500"></i>${e.location}</span>` : ''}
                        ${e.attendees ? `<span><i data-lucide="users" class="w-3 h-3 inline mr-1 text-slate-500"></i>${e.attendees}</span>` : ''}
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        } catch (e) {
            console.error('Failed to fetch calendar:', e);
        }
    }

    async fetchMemories() {
        try {
            const res = await fetch('/api/memories');
            const data = await res.json();
            this.memoriesCount.textContent = `${data.count} Notes`;

            if (data.memories.length === 0) {
                this.memoriesList.innerHTML = `<div class="text-center py-4 text-xs text-slate-500">No saved preferences yet.</div>`;
                return;
            }

            this.memoriesList.innerHTML = data.memories.map(m => `
                <div class="p-2.5 rounded-xl bg-slate-900/30 border border-cardborder text-xs">
                    <span class="text-[10px] font-mono uppercase text-purple-400">${m.key}</span>
                    <p class="text-slate-300 text-[11px] mt-0.5">${m.content}</p>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to fetch memories:', e);
        }
    }

    async fetchRagDocs() {
        try {
            const res = await fetch('/api/rag/documents');
            const data = await res.json();
            this.ragDocsCount.textContent = `${data.count} Docs`;

            if (data.documents.length === 0) {
                this.ragDocsList.innerHTML = `<div class="text-center py-4 text-xs text-slate-500">No ingested documents.</div>`;
                return;
            }

            this.ragDocsList.innerHTML = data.documents.map(d => `
                <div class="p-2.5 rounded-xl bg-slate-900/40 border border-cardborder text-xs hover:border-slate-700 transition-colors">
                    <div class="flex items-center justify-between">
                        <span class="font-medium text-slate-200 text-xs truncate">${d.title}</span>
                        <span class="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">${d.chunk_count} chunks</span>
                    </div>
                    <p class="text-slate-500 text-[10px] mt-1">Category: ${d.category} ${d.filename ? `• ${d.filename}` : ''}</p>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to fetch RAG docs:', e);
        }
    }
}

// Instantiate global client
let agentApp;
window.addEventListener('DOMContentLoaded', () => {
    agentApp = new VoiceAgentClient();
});
