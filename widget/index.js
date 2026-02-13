/**
 * SvontAi Chat Widget
 * Lightweight, embeddable chat widget with Shadow DOM isolation.
 *
 * Usage:
 * <script src="https://your-domain.com/widget.js" data-bot-key="YOUR_BOT_PUBLIC_KEY"></script>
 * Optional:
 * <script src="..." data-bot-key="..." data-api-url="https://api.your-domain.com"></script>
 */

(function() {
  'use strict';

  const DEFAULT_API_URL = 'http://localhost:8000';
  const scriptTag = document.currentScript || document.querySelector('script[data-bot-key]');
  const botPublicKey = scriptTag?.getAttribute('data-bot-key');

  if (!botPublicKey) {
    console.error('SvontAi Widget: data-bot-key attribute is required');
    return;
  }

  const apiUrl = scriptTag?.getAttribute('data-api-url')
    || (scriptTag?.src ? new URL(scriptTag.src, window.location.href).origin : DEFAULT_API_URL);
  const storageKey = `smartwa_user_id:${botPublicKey}`;
  const legacyStorageKey = 'smartwa_user_id';

  let storedExternalId = null;
  try {
    storedExternalId = localStorage.getItem(storageKey) || localStorage.getItem(legacyStorageKey);
  } catch (error) {
    storedExternalId = null;
  }

  const messageIds = new Set();
  const state = {
    isOpen: false,
    isInitialized: false,
    isLoading: false,
    conversationId: null,
    externalUserId: storedExternalId,
    botInfo: null,
    messages: [],
    lastServerTimestamp: null,
    pendingMessageId: null,
    unreadCount: 0,
    pollingTimer: null,
    pollingInterval: 12000,
    conversationStatus: 'ai_active',
    isAiPaused: false,
    lastStatusMode: null,
    welcomeMessage: null
  };

  const styles = `
    :host {
      all: initial;
      font-family: var(--sw-font, "Space Grotesk", "Segoe UI", sans-serif);
      color: #0f172a;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    .smartwa-container {
      position: fixed;
      bottom: calc(20px + env(safe-area-inset-bottom));
      z-index: 999999;
    }

    .smartwa-container.right {
      right: 20px;
    }

    .smartwa-container.left {
      left: 20px;
    }

    .smartwa-button {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      border: none;
      cursor: pointer;
      display: grid;
      place-items: center;
      color: white;
      background: var(--sw-primary-gradient);
      box-shadow: var(--sw-primary-shadow);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      position: relative;
      animation: buttonFloat 3s ease-in-out infinite;
    }

    @keyframes buttonFloat {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    .smartwa-button:hover {
      transform: translateY(-2px) scale(1.04);
      box-shadow: 0 16px 36px rgba(15, 23, 42, 0.18);
      animation: none;
    }

    .smartwa-button svg {
      width: 30px;
      height: 30px;
    }

    .smartwa-unread {
      position: absolute;
      top: 6px;
      right: 6px;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      border-radius: 999px;
      background: #f97316;
      color: white;
      font-size: 11px;
      font-weight: 600;
      display: none;
      align-items: center;
      justify-content: center;
      box-shadow: 0 6px 16px rgba(249, 115, 22, 0.35);
    }

    .smartwa-unread.visible {
      display: flex;
    }

    .smartwa-window {
      position: absolute;
      bottom: 82px;
      width: 380px;
      max-width: calc(100vw - 40px);
      height: min(540px, calc(100vh - 140px));
      background: white;
      border-radius: 22px;
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.2);
      display: none;
      flex-direction: column;
      overflow: hidden;
      border: 1px solid rgba(148, 163, 184, 0.25);
    }

    .smartwa-container.right .smartwa-window {
      right: 0;
    }

    .smartwa-container.left .smartwa-window {
      left: 0;
    }

    .smartwa-window.open {
      display: flex;
      animation: slideUp 0.2s ease;
    }

    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(16px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .smartwa-header {
      padding: 18px 20px;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--sw-primary-gradient);
    }

    .smartwa-header-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .smartwa-avatar {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.18);
      display: grid;
      place-items: center;
      color: white;
    }

    .smartwa-avatar svg {
      width: 22px;
      height: 22px;
    }

    .smartwa-header-text h3 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 2px;
      letter-spacing: -0.2px;
    }

    .smartwa-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      opacity: 0.9;
    }

    .smartwa-status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #22c55e;
      box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.25);
    }

    .smartwa-status[data-mode="human"] .smartwa-status-dot {
      background: #f97316;
      box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.25);
    }

    .smartwa-close {
      background: none;
      border: none;
      cursor: pointer;
      padding: 6px;
      border-radius: 10px;
      color: white;
      transition: background 0.2s ease;
    }

    .smartwa-close:hover {
      background: rgba(255, 255, 255, 0.18);
    }

    .smartwa-close svg {
      width: 20px;
      height: 20px;
    }

    .smartwa-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.1), transparent 45%),
        #f8fafc;
    }

    .smartwa-message {
      max-width: 84%;
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
      position: relative;
    }

    .smartwa-message.bot {
      align-self: flex-start;
      background: white;
      border: 1px solid #e2e8f0;
      border-bottom-left-radius: 6px;
    }

    .smartwa-message.operator {
      align-self: flex-start;
      background: #fff7ed;
      border: 1px solid #fed7aa;
      color: #7c2d12;
      border-bottom-left-radius: 6px;
    }

    .smartwa-message.user {
      align-self: flex-end;
      color: white;
      background: var(--sw-primary-solid);
      border-bottom-right-radius: 6px;
    }

    .smartwa-message.system {
      align-self: center;
      background: transparent;
      color: #64748b;
      font-size: 12px;
      padding: 8px 12px;
      border: 1px dashed #cbd5f5;
    }

    .smartwa-message.pending {
      opacity: 0.7;
    }

    .smartwa-message.failed {
      border-color: #f87171;
      color: #b91c1c;
    }

    .smartwa-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      margin-bottom: 6px;
      color: #ea580c;
    }

    .smartwa-typing {
      align-self: flex-start;
      background: white;
      border: 1px solid #e2e8f0;
      padding: 12px 16px;
      border-radius: 16px;
      border-bottom-left-radius: 6px;
      display: flex;
      gap: 4px;
    }

    .smartwa-typing span {
      width: 8px;
      height: 8px;
      background: #94a3b8;
      border-radius: 50%;
      animation: bounce 1.2s infinite ease-in-out;
    }

    .smartwa-typing span:nth-child(1) { animation-delay: -0.32s; }
    .smartwa-typing span:nth-child(2) { animation-delay: -0.16s; }

    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }

    .smartwa-input-area {
      padding: 14px 16px 16px;
      background: white;
      border-top: 1px solid #e2e8f0;
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }

    .smartwa-input {
      flex: 1;
      min-height: 44px;
      max-height: 120px;
      padding: 10px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.4;
      outline: none;
      resize: none;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .smartwa-input:focus {
      border-color: rgba(14, 116, 144, 0.4);
      box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.2);
    }

    .smartwa-send {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      border: none;
      cursor: pointer;
      display: grid;
      place-items: center;
      background: var(--sw-primary-solid);
      color: white;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .smartwa-send:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 18px rgba(15, 23, 42, 0.16);
    }

    .smartwa-send:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      box-shadow: none;
      transform: none;
    }

    .smartwa-send svg {
      width: 18px;
      height: 18px;
    }

    @media (max-width: 480px) {
      .smartwa-window {
        width: 100%;
        max-width: none;
        height: calc(100vh - 90px);
        border-radius: 20px 20px 0 0;
        bottom: 72px;
        left: 0;
        right: 0;
      }

      .smartwa-container.left .smartwa-window,
      .smartwa-container.right .smartwa-window {
        left: 0;
        right: 0;
      }

      .smartwa-container {
        right: 16px;
        left: auto;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .smartwa-button,
      .smartwa-window {
        animation: none;
        transition: none;
      }

      .smartwa-typing span {
        animation: none;
      }
    }
  `;

  const icons = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 14.5a5 5 0 0 1-5 5H8l-5 4V6.5a5 5 0 0 1 5-5h8a5 5 0 0 1 5 5z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 6l12 12M6 18L18 6"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 11.5l17-8-6.5 17-2.5-7-8-2z"/></svg>',
    bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="7" width="16" height="12" rx="4"/><path d="M9 7V4m6 3V4"/><circle cx="9" cy="13" r="1.5"/><circle cx="15" cy="13" r="1.5"/></svg>'
  };

  function parseHexColor(color) {
    if (!color || color[0] !== '#') return null;
    const hex = color.replace('#', '').trim();
    if (hex.length === 3) {
      const r = parseInt(hex[0] + hex[0], 16);
      const g = parseInt(hex[1] + hex[1], 16);
      const b = parseInt(hex[2] + hex[2], 16);
      return { r, g, b };
    }
    if (hex.length === 6) {
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return { r, g, b };
    }
    return null;
  }

  function mixColor(color, target, ratio) {
    return {
      r: Math.round(color.r + (target.r - color.r) * ratio),
      g: Math.round(color.g + (target.g - color.g) * ratio),
      b: Math.round(color.b + (target.b - color.b) * ratio)
    };
  }

  function rgbToString(color) {
    return `rgb(${color.r}, ${color.g}, ${color.b})`;
  }

  function rgbaToString(color, alpha) {
    return `rgba(${color.r}, ${color.g}, ${color.b}, ${alpha})`;
  }

  function buildPalette(primaryColor) {
    const fallback = '#2563eb';
    const isGradient = typeof primaryColor === 'string' && primaryColor.includes('gradient');
    const baseColor = isGradient ? fallback : (primaryColor || fallback);
    const rgb = parseHexColor(baseColor);

    if (!rgb) {
      return {
        solid: baseColor,
        gradient: isGradient ? primaryColor : baseColor,
        shadow: '0 12px 30px rgba(37, 99, 235, 0.35)'
      };
    }

    const lighter = mixColor(rgb, { r: 255, g: 255, b: 255 }, 0.2);
    const darker = mixColor(rgb, { r: 0, g: 0, b: 0 }, 0.18);

    return {
      solid: rgbToString(rgb),
      gradient: isGradient ? primaryColor : `linear-gradient(135deg, ${rgbToString(lighter)} 0%, ${rgbToString(rgb)} 50%, ${rgbToString(darker)} 100%)`,
      shadow: `0 12px 30px ${rgbaToString(rgb, 0.35)}`
    };
  }

  const container = document.createElement('div');
  let shadow = null;

  function ensureMounted() {
    if (shadow || !document.body) return;
    container.id = 'smartwa-widget';
    shadow = container.attachShadow({ mode: 'closed' });
    document.body.appendChild(container);
  }

  function createWidget(botInfo) {
    const palette = buildPalette(botInfo?.primary_color);
    const position = botInfo?.widget_position || 'right';
    const botName = botInfo?.name || 'AI Asistan';

    ensureMounted();
    shadow.innerHTML = `
      <style>
        :host {
          --sw-primary-solid: ${palette.solid};
          --sw-primary-gradient: ${palette.gradient};
          --sw-primary-shadow: ${palette.shadow};
        }
        ${styles}
      </style>
      <div class="smartwa-container ${position}">
        <div class="smartwa-window" id="smartwa-window" aria-hidden="true">
          <div class="smartwa-header">
            <div class="smartwa-header-info">
              <div class="smartwa-avatar">${icons.bot}</div>
              <div class="smartwa-header-text">
                <h3>${botName}</h3>
                <div class="smartwa-status" id="smartwa-status" data-mode="ai">
                  <span class="smartwa-status-dot"></span>
                  <span id="smartwa-status-text">Asistan çevrimiçi</span>
                </div>
              </div>
            </div>
            <button class="smartwa-close" id="smartwa-close" aria-label="Kapat">${icons.close}</button>
          </div>
          <div class="smartwa-messages" id="smartwa-messages"></div>
          <div class="smartwa-input-area">
            <textarea class="smartwa-input" id="smartwa-input" rows="1" placeholder="Mesajınızı yazın..."></textarea>
            <button class="smartwa-send" id="smartwa-send" aria-label="Gönder">${icons.send}</button>
          </div>
        </div>
        <button class="smartwa-button" id="smartwa-button" aria-label="Sohbeti aç">
          ${icons.chat}
          <span class="smartwa-unread" id="smartwa-unread">0</span>
        </button>
      </div>
    `;

    bindEvents();
  }

  function bindEvents() {
    const button = shadow.getElementById('smartwa-button');
    const closeBtn = shadow.getElementById('smartwa-close');
    const input = shadow.getElementById('smartwa-input');
    const sendBtn = shadow.getElementById('smartwa-send');
    if (!input || !sendBtn) return;

    button.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);
    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
    input.addEventListener('input', () => autoResize(input));
  }

  function autoResize(input) {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }

  function toggleChat() {
    state.isOpen = !state.isOpen;
    const windowEl = shadow.getElementById('smartwa-window');
    const button = shadow.getElementById('smartwa-button');

    if (state.isOpen) {
      windowEl.classList.add('open');
      windowEl.setAttribute('aria-hidden', 'false');
      button.innerHTML = `${icons.close}<span class="smartwa-unread" id="smartwa-unread">0</span>`;
      state.unreadCount = 0;
      updateUnread();
      renderMessages();
      setPollingMode(true);
      fetchMessages();
      focusInput();
    } else {
      windowEl.classList.remove('open');
      windowEl.setAttribute('aria-hidden', 'true');
      button.innerHTML = `${icons.chat}<span class="smartwa-unread" id="smartwa-unread">0</span>`;
      setPollingMode(false);
      updateUnread();
    }
  }

  function focusInput() {
    if (!shadow) return;
    const input = shadow.getElementById('smartwa-input');
    if (input) {
      input.focus();
    }
  }

  function setPollingMode(isOpen) {
    const interval = isOpen ? 4000 : 12000;
    if (state.pollingInterval === interval && state.pollingTimer) return;
    state.pollingInterval = interval;
    stopPolling();
    state.pollingTimer = setInterval(fetchMessages, state.pollingInterval);
  }

  function stopPolling() {
    if (state.pollingTimer) {
      clearInterval(state.pollingTimer);
      state.pollingTimer = null;
    }
  }

  function updateUnread() {
    if (!shadow) return;
    const unreadEl = shadow.getElementById('smartwa-unread');
    if (!unreadEl) return;

    if (state.unreadCount > 0) {
      unreadEl.textContent = state.unreadCount > 9 ? '9+' : `${state.unreadCount}`;
      unreadEl.classList.add('visible');
    } else {
      unreadEl.textContent = '0';
      unreadEl.classList.remove('visible');
    }
  }

  function updateLastServerTimestamp(timestamp) {
    if (!timestamp) return;
    if (!state.lastServerTimestamp || new Date(timestamp) > new Date(state.lastServerTimestamp)) {
      state.lastServerTimestamp = timestamp;
    }
  }

  function applyStatus(status, isAiPaused) {
    if (status) state.conversationStatus = status;
    if (typeof isAiPaused === 'boolean') state.isAiPaused = isAiPaused;

    if (!shadow) return;
    const statusEl = shadow.getElementById('smartwa-status');
    const textEl = shadow.getElementById('smartwa-status-text');
    if (!statusEl || !textEl) return;

    const mode = state.isAiPaused || state.conversationStatus === 'human_takeover' ? 'human' : 'ai';
    statusEl.dataset.mode = mode;
    textEl.textContent = mode === 'human' ? 'Canlı destek devrede' : 'Asistan çevrimiçi';

    if (state.lastStatusMode && state.lastStatusMode !== mode) {
      addSystemMessage(
        mode === 'human'
          ? 'Canlı destek ekibi devreye girdi. Mesajınızı görüyor.'
          : 'AI tekrar aktif. Size yardımcı olmaya devam ediyor.'
      );
    }
    state.lastStatusMode = mode;
  }

  function addMessage(message) {
    state.messages.push(message);
    renderMessages();
  }

  function addSystemMessage(text) {
    addMessage({
      id: `system-${Date.now()}`,
      sender: 'system',
      content: text,
      created_at: new Date().toISOString()
    });
  }

  function renderMessages() {
    if (!shadow) return;
    const messagesContainer = shadow.getElementById('smartwa-messages');
    if (!messagesContainer) return;

    messagesContainer.innerHTML = '';
    state.messages.forEach((message) => {
      const messageEl = document.createElement('div');
      messageEl.className = `smartwa-message ${message.sender}`;
      messageEl.dataset.id = message.id;

      if (message.status === 'pending') {
        messageEl.classList.add('pending');
      }
      if (message.status === 'failed') {
        messageEl.classList.add('failed');
      }

      if (message.sender === 'operator') {
        const badge = document.createElement('div');
        badge.className = 'smartwa-badge';
        badge.textContent = 'Canlı Destek';
        messageEl.appendChild(badge);
      }

      messageEl.appendChild(document.createTextNode(message.content));
      messagesContainer.appendChild(messageEl);
    });

    if (state.isLoading) {
      const typingEl = document.createElement('div');
      typingEl.className = 'smartwa-typing';
      typingEl.innerHTML = '<span></span><span></span><span></span>';
      messagesContainer.appendChild(typingEl);
    }

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function confirmPendingMessage(serverId, createdAt) {
    if (!state.pendingMessageId) return false;

    const pendingId = state.pendingMessageId;
    state.pendingMessageId = null;
    messageIds.add(serverId);

    state.messages = state.messages.map((message) => {
      if (message.id === pendingId) {
        return {
          ...message,
          id: serverId,
          created_at: createdAt,
          status: null
        };
      }
      return message;
    });

    updateLastServerTimestamp(createdAt);
    renderMessages();
    return true;
  }

  async function fetchMessages() {
    if (!state.conversationId || !state.externalUserId) return;

    const params = new URLSearchParams({
      conversation_id: state.conversationId,
      external_user_id: state.externalUserId
    });

    if (state.lastServerTimestamp) {
      params.append('since', state.lastServerTimestamp);
    }

    try {
      if (!shadow) return;
      const response = await fetch(`${apiUrl}/public/chat/messages?${params.toString()}`);
      if (!response.ok) return;
      const data = await response.json();

      applyStatus(data.conversation_status, data.is_ai_paused);

      if (Array.isArray(data.messages)) {
        data.messages.forEach((message) => {
          const messageId = String(message.id);

          if (messageIds.has(messageId)) return;
          if (message.sender === 'user' && state.pendingMessageId) {
            if (confirmPendingMessage(messageId, message.created_at)) return;
          }

          messageIds.add(messageId);
          state.messages.push({
            id: messageId,
            sender: message.sender,
            content: message.content,
            created_at: message.created_at
          });

          if (!state.isOpen && message.sender !== 'user') {
            state.unreadCount += 1;
          }
        });

        if (data.messages.length > 0) {
          updateLastServerTimestamp(data.messages[data.messages.length - 1].created_at);
        }
      }

      if (state.messages.length === 0 && state.welcomeMessage) {
        addMessage({
          id: `welcome-${state.conversationId}`,
          sender: 'bot',
          content: state.welcomeMessage,
          created_at: new Date().toISOString()
        });
      } else {
        renderMessages();
      }

      updateUnread();
    } catch (error) {
      console.error('SvontAi: Failed to fetch messages', error);
    }
  }

  async function initializeConversation() {
    const response = await fetch(`${apiUrl}/public/chat/init`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        bot_public_key: botPublicKey,
        external_user_id: state.externalUserId
      })
    });

    if (!response.ok) throw new Error('Failed to initialize chat');
    const data = await response.json();

    state.conversationId = data.conversation_id;
    state.externalUserId = data.external_user_id;
    state.botInfo = data.bot;
    state.isInitialized = true;
    state.welcomeMessage = data.welcome_message;
    applyStatus(data.conversation_status, data.is_ai_paused);

    try {
      localStorage.setItem(storageKey, data.external_user_id);
      localStorage.removeItem(legacyStorageKey);
    } catch (error) {
      // Ignore storage errors
    }

    return data;
  }

  async function sendMessage() {
    if (!shadow) return;
    const input = shadow.getElementById('smartwa-input');
    const sendBtn = shadow.getElementById('smartwa-send');
    const messageText = input.value.trim();

    if (!messageText || state.isLoading || !state.conversationId) return;

    const localId = `pending-${Date.now()}`;
    state.pendingMessageId = localId;

    addMessage({
      id: localId,
      sender: 'user',
      content: messageText,
      created_at: new Date().toISOString(),
      status: 'pending'
    });

    input.value = '';
    autoResize(input);
    state.isLoading = true;
    sendBtn.disabled = true;
    renderMessages();

    try {
      const response = await fetch(`${apiUrl}/public/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: state.conversationId,
          message: messageText
        })
      });

      if (!response.ok) throw new Error('Failed to send message');
      const data = await response.json();

      applyStatus(data.conversation_status, data.is_ai_paused);

      confirmPendingMessage(String(data.user_message_id), data.user_created_at);

      if (data.reply) {
        const replyId = data.reply_message_id ? String(data.reply_message_id) : `bot-${Date.now()}`;
        if (!messageIds.has(replyId)) {
          messageIds.add(replyId);
          addMessage({
            id: replyId,
            sender: 'bot',
            content: data.reply,
            created_at: data.reply_created_at || new Date().toISOString()
          });
        }
        updateLastServerTimestamp(data.reply_created_at);
      }
    } catch (error) {
      state.pendingMessageId = null;
      state.messages = state.messages.map((message) => {
        if (message.id === localId) {
          return { ...message, status: 'failed' };
        }
        return message;
      });
      addSystemMessage('Mesaj gönderilemedi. Lütfen tekrar deneyin.');
      console.error('SvontAi: Failed to send message', error);
    } finally {
      state.isLoading = false;
      sendBtn.disabled = false;
      renderMessages();
    }
  }

  async function init() {
    try {
      const data = await initializeConversation();
      ensureMounted();
      createWidget(data.bot);
      applyStatus(data.conversation_status, data.is_ai_paused);
      await fetchMessages();
      setPollingMode(false);
    } catch (error) {
      console.error('SvontAi: Failed to load widget', error);
      createWidget(null);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
