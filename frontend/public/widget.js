/**
 * SvontAi Chat Widget
 * A lightweight, embeddable chat widget using Shadow DOM
 * 
 * Usage:
 * <script src="https://your-domain.com/widget.js" data-bot-key="YOUR_BOT_PUBLIC_KEY"></script>
 */

(function() {
  'use strict';

  // Configuration
  const API_URL = 'http://localhost:8000'; // Change this to your backend URL
  
  // Get bot key from script tag
  const scriptTag = document.currentScript;
  const botPublicKey = scriptTag?.getAttribute('data-bot-key');
  
  if (!botPublicKey) {
    console.error('SvontAi Widget: data-bot-key attribute is required');
    return;
  }

  // Widget state
  let state = {
    isOpen: false,
    isInitialized: false,
    isLoading: false,
    conversationId: null,
    externalUserId: localStorage.getItem('svontai_user_id'),
    botInfo: null,
    messages: []
  };

  // Create widget styles
  const styles = `
    :host {
      all: initial;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    }
    
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    
    .svontai-container {
      position: fixed;
      bottom: 20px;
      z-index: 999999;
    }
    
    .svontai-container.right {
      right: 20px;
    }
    
    .svontai-container.left {
      left: 20px;
    }
    
    .svontai-button {
      width: 64px;
      height: 64px;
      border-radius: 50%;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 24px rgba(168, 85, 247, 0.4);
      transition: transform 0.3s, box-shadow 0.3s;
      animation: buttonPulse 2s ease-in-out infinite;
    }
    
    @keyframes buttonPulse {
      0%, 100% { box-shadow: 0 4px 24px rgba(168, 85, 247, 0.4); }
      50% { box-shadow: 0 6px 32px rgba(168, 85, 247, 0.6); }
    }
    
    .svontai-button:hover {
      transform: scale(1.1);
      box-shadow: 0 8px 32px rgba(168, 85, 247, 0.6);
      animation: none;
    }
    
    .svontai-button svg {
      width: 36px;
      height: 36px;
    }
    
    .svontai-window {
      position: absolute;
      bottom: 80px;
      width: 380px;
      max-width: calc(100vw - 40px);
      height: 520px;
      max-height: calc(100vh - 120px);
      background: white;
      border-radius: 20px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
      display: none;
      flex-direction: column;
      overflow: hidden;
    }
    
    .svontai-container.right .svontai-window {
      right: 0;
    }
    
    .svontai-container.left .svontai-window {
      left: 0;
    }
    
    .svontai-window.open {
      display: flex;
      animation: slideUp 0.3s ease;
    }
    
    @keyframes slideUp {
      from {
        opacity: 0;
        transform: translateY(20px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    .svontai-header {
      padding: 16px 20px;
      color: white;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    
    .svontai-header-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    
    .svontai-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .svontai-avatar svg {
      width: 20px;
      height: 20px;
      fill: white;
    }
    
    .svontai-header-text h3 {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 2px;
    }
    
    .svontai-header-text p {
      font-size: 12px;
      opacity: 0.8;
    }
    
    .svontai-close {
      background: none;
      border: none;
      cursor: pointer;
      padding: 8px;
      border-radius: 50%;
      transition: background 0.2s;
    }
    
    .svontai-close:hover {
      background: rgba(255, 255, 255, 0.1);
    }
    
    .svontai-close svg {
      width: 20px;
      height: 20px;
      fill: white;
    }
    
    .svontai-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: #f8fafc;
    }
    
    .svontai-message {
      max-width: 80%;
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    }
    
    .svontai-message.bot {
      align-self: flex-start;
      background: white;
      border: 1px solid #e2e8f0;
      border-bottom-left-radius: 4px;
    }
    
    .svontai-message.user {
      align-self: flex-end;
      color: white;
      border-bottom-right-radius: 4px;
    }
    
    .svontai-typing {
      align-self: flex-start;
      background: white;
      border: 1px solid #e2e8f0;
      padding: 12px 16px;
      border-radius: 16px;
      border-bottom-left-radius: 4px;
      display: flex;
      gap: 4px;
    }
    
    .svontai-typing span {
      width: 8px;
      height: 8px;
      background: #94a3b8;
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out;
    }
    
    .svontai-typing span:nth-child(1) { animation-delay: -0.32s; }
    .svontai-typing span:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    
    .svontai-input-area {
      padding: 16px;
      background: white;
      border-top: 1px solid #e2e8f0;
      display: flex;
      gap: 12px;
    }
    
    .svontai-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid #e2e8f0;
      border-radius: 24px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    
    .svontai-input:focus {
      border-color: #94a3b8;
    }
    
    .svontai-send {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s;
    }
    
    .svontai-send:hover {
      transform: scale(1.05);
    }
    
    .svontai-send:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    
    .svontai-send svg {
      width: 20px;
      height: 20px;
      fill: white;
    }
    
    .svontai-powered {
      text-align: center;
      padding: 8px;
      font-size: 11px;
      color: #94a3b8;
      background: white;
      border-top: 1px solid #f1f5f9;
    }
    
    .svontai-powered a {
      color: #a855f7;
      text-decoration: none;
      font-weight: 500;
    }
    
    @media (max-width: 480px) {
      .svontai-window {
        width: 100%;
        max-width: none;
        height: calc(100vh - 100px);
        max-height: none;
        border-radius: 20px 20px 0 0;
        bottom: 70px;
        left: 0;
        right: 0;
      }
      
      .svontai-container.left .svontai-window,
      .svontai-container.right .svontai-window {
        left: 0;
        right: 0;
      }
    }
  `;

  // SVG Icons - SvontAi Brand Logo
  const icons = {
    chat: `<svg viewBox="0 0 100 100" fill="none">
      <defs>
        <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f472b6"/>
          <stop offset="50%" stop-color="#a855f7"/>
          <stop offset="100%" stop-color="#3b82f6"/>
        </linearGradient>
        <linearGradient id="barGrad" x1="0%" y1="100%" x2="0%" y2="0%">
          <stop offset="0%" stop-color="#60a5fa"/>
          <stop offset="100%" stop-color="#f472b6"/>
        </linearGradient>
      </defs>
      <path d="M20 15 C20 10, 25 5, 35 5 L65 5 C75 5, 80 10, 80 15 L80 55 C80 60, 75 65, 65 65 L40 65 L25 80 L25 65 L35 65 C25 65, 20 60, 20 55 Z" stroke="url(#logoGrad)" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M35 25 L35 45 C35 50, 40 52, 45 48" stroke="url(#barGrad)" stroke-width="5" stroke-linecap="round" fill="none"/>
      <line x1="52" y1="22" x2="52" y2="50" stroke="url(#barGrad)" stroke-width="5" stroke-linecap="round"/>
      <circle cx="65" cy="45" r="4" fill="url(#barGrad)"/>
    </svg>`,
    close: '<svg viewBox="0 0 24 24" fill="white"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>',
    bot: `<svg viewBox="0 0 100 100" fill="none">
      <defs>
        <linearGradient id="botGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#f472b6"/>
          <stop offset="50%" stop-color="#a855f7"/>
          <stop offset="100%" stop-color="#3b82f6"/>
        </linearGradient>
      </defs>
      <path d="M20 15 C20 10, 25 5, 35 5 L65 5 C75 5, 80 10, 80 15 L80 55 C80 60, 75 65, 65 65 L40 65 L25 80 L25 65 L35 65 C25 65, 20 60, 20 55 Z" stroke="url(#botGrad)" stroke-width="4" fill="none" stroke-linecap="round"/>
      <path d="M35 25 L35 45 C35 50, 40 52, 45 48" stroke="url(#botGrad)" stroke-width="5" stroke-linecap="round" fill="none"/>
      <line x1="52" y1="22" x2="52" y2="50" stroke="url(#botGrad)" stroke-width="5" stroke-linecap="round"/>
      <circle cx="65" cy="45" r="4" fill="url(#botGrad)"/>
    </svg>`
  };

  // Create shadow DOM container
  const container = document.createElement('div');
  container.id = 'svontai-widget';
  const shadow = container.attachShadow({ mode: 'closed' });
  document.body.appendChild(container);

  // Create widget HTML
  function createWidget(botInfo) {
    const primaryColor = botInfo?.primary_color || 'linear-gradient(135deg, #f472b6, #a855f7, #3b82f6)';
    const position = botInfo?.widget_position || 'right';
    const botName = botInfo?.name || 'AI Asistan';
    
    shadow.innerHTML = `
      <style>${styles}</style>
      <div class="svontai-container ${position}">
        <div class="svontai-window" id="svontai-window">
          <div class="svontai-header" style="background: ${primaryColor}">
            <div class="svontai-header-info">
              <div class="svontai-avatar">${icons.bot}</div>
              <div class="svontai-header-text">
                <h3>${botName}</h3>
                <p>Çevrimiçi</p>
              </div>
            </div>
            <button class="svontai-close" id="svontai-close">${icons.close}</button>
          </div>
          <div class="svontai-messages" id="svontai-messages"></div>
          <div class="svontai-input-area">
            <input type="text" class="svontai-input" id="svontai-input" placeholder="Mesajınızı yazın...">
            <button class="svontai-send" id="svontai-send" style="background: ${primaryColor}">${icons.send}</button>
          </div>
          <div class="svontai-powered">
            Powered by <a href="https://svontai.com" target="_blank">SvontAi</a>
          </div>
        </div>
        <button class="svontai-button" id="svontai-button" style="background: ${primaryColor}">${icons.chat}</button>
      </div>
    `;
    
    // Bind events
    bindEvents(primaryColor);
  }

  // Bind event listeners
  function bindEvents(primaryColor) {
    const button = shadow.getElementById('svontai-button');
    const closeBtn = shadow.getElementById('svontai-close');
    const chatWindow = shadow.getElementById('svontai-window');
    const input = shadow.getElementById('svontai-input');
    const sendBtn = shadow.getElementById('svontai-send');
    
    button.addEventListener('click', () => toggleChat(primaryColor));
    closeBtn.addEventListener('click', () => toggleChat(primaryColor));
    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMessage();
    });
  }

  // Toggle chat window
  function toggleChat(primaryColor) {
    state.isOpen = !state.isOpen;
    const chatWindow = shadow.getElementById('svontai-window');
    const button = shadow.getElementById('svontai-button');
    
    if (state.isOpen) {
      chatWindow.classList.add('open');
      button.innerHTML = icons.close;
      
      if (!state.isInitialized) {
        initializeChat(primaryColor);
      }
    } else {
      chatWindow.classList.remove('open');
      button.innerHTML = icons.chat;
    }
  }

  // Initialize chat session
  async function initializeChat(primaryColor) {
    try {
      const response = await fetch(`${API_URL}/public/chat/init`, {
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
      
      localStorage.setItem('svontai_user_id', data.external_user_id);
      
      // Add welcome message
      addMessage(data.welcome_message, 'bot', primaryColor);
    } catch (error) {
      console.error('SvontAi: Failed to initialize chat', error);
      addMessage('Bağlantı hatası. Lütfen daha sonra tekrar deneyin.', 'bot', primaryColor);
    }
  }

  // Send message
  async function sendMessage() {
    const input = shadow.getElementById('svontai-input');
    const sendBtn = shadow.getElementById('svontai-send');
    const message = input.value.trim();
    const primaryColor = state.botInfo?.primary_color || '#3C82F6';
    
    if (!message || state.isLoading || !state.conversationId) return;
    
    // Add user message
    addMessage(message, 'user', primaryColor);
    input.value = '';
    
    // Show typing indicator
    state.isLoading = true;
    sendBtn.disabled = true;
    showTyping();
    
    try {
      const response = await fetch(`${API_URL}/public/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: state.conversationId,
          message: message
        })
      });
      
      if (!response.ok) throw new Error('Failed to send message');
      
      const data = await response.json();
      hideTyping();
      addMessage(data.reply, 'bot', primaryColor);
    } catch (error) {
      console.error('SvontAi: Failed to send message', error);
      hideTyping();
      addMessage('Mesaj gönderilemedi. Lütfen tekrar deneyin.', 'bot', primaryColor);
    } finally {
      state.isLoading = false;
      sendBtn.disabled = false;
    }
  }

  // Add message to chat
  function addMessage(text, sender, primaryColor) {
    const messagesContainer = shadow.getElementById('svontai-messages');
    const messageEl = document.createElement('div');
    messageEl.className = `svontai-message ${sender}`;
    messageEl.textContent = text;
    
    if (sender === 'user') {
      messageEl.style.background = primaryColor;
    }
    
    messagesContainer.appendChild(messageEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Show typing indicator
  function showTyping() {
    const messagesContainer = shadow.getElementById('svontai-messages');
    const typingEl = document.createElement('div');
    typingEl.className = 'svontai-typing';
    typingEl.id = 'svontai-typing';
    typingEl.innerHTML = '<span></span><span></span><span></span>';
    messagesContainer.appendChild(typingEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // Hide typing indicator
  function hideTyping() {
    const typingEl = shadow.getElementById('svontai-typing');
    if (typingEl) typingEl.remove();
  }

  // Initialize widget
  async function init() {
    try {
      // Fetch bot info first to get styling
      const response = await fetch(`${API_URL}/public/chat/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bot_public_key: botPublicKey,
          external_user_id: state.externalUserId
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        state.conversationId = data.conversation_id;
        state.externalUserId = data.external_user_id;
        state.botInfo = data.bot;
        state.isInitialized = true;
        localStorage.setItem('svontai_user_id', data.external_user_id);
        
        createWidget(data.bot);
        
        // Pre-add welcome message when opened
        state.messages.push({ text: data.welcome_message, sender: 'bot' });
      } else {
        // Create widget with defaults if init fails
        createWidget(null);
      }
    } catch (error) {
      console.error('SvontAi: Failed to load widget', error);
      createWidget(null);
    }
  }

  // Start widget when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

