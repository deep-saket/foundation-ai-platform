const personaSelect = document.getElementById('persona');
const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const promptInput = document.getElementById('prompt-input');
const sendBtn = document.getElementById('send-btn');
const personaTitle = document.getElementById('current-persona-title');
const personaDesc = document.getElementById('current-persona-desc');

const API_URL = "http://localhost:8000/v1/chat/completions";

// Shared conversation history across all model/capability switches
let conversationHistory = [];

const personaData = {
    "chat": {
        title: "Tyrion Lannister",
        desc: "I drink and I know things. (General Chat)",
        icon: "fa-wine-glass"
    },
    "math": {
        title: "Euclid",
        desc: "The father of geometry. (Mathematics)",
        icon: "fa-square-root-variable"
    },
    "reasoning": {
        title: "Socrates",
        desc: "I know that I know nothing. (Deep Reasoning)",
        icon: "fa-brain"
    },
    "summarization": {
        title: "TL;DR",
        desc: "Get straight to the point. (Summarization)",
        icon: "fa-compress-alt"
    }
};

// Auto-resize textarea
promptInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if (this.value === '') {
        this.style.height = 'auto';
    }
});

// Handle enter to submit
promptInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// Change Persona UI
personaSelect.addEventListener('change', (e) => {
    const capability = e.target.value;
    const data = personaData[capability];
    personaTitle.innerHTML = `<i class="fas ${data.icon}"></i> ${data.title}`;
    personaDesc.textContent = data.desc;
    // Context is intentionally preserved across persona switches
});

// Clear Context Button
document.getElementById('clear-context-btn').addEventListener('click', () => {
    conversationHistory = [];
    chatHistory.innerHTML = `
        <div class="message system-message fade-in">
            <div class="avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">Context cleared. Starting a fresh conversation.</div>
        </div>
    `;
});

// Create Message Element
function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message fade-in`;
    
    const icon = role === 'user' ? 'fa-user' : 'fa-robot';
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fas ${icon}"></i></div>
        <div class="message-content">${escapeHTML(content)}</div>
    `;
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Create Typing Indicator
function appendTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message system-message fade-in`;
    msgDiv.id = 'typing-indicator';
    
    msgDiv.innerHTML = `
        <div class="avatar"><i class="fas fa-robot"></i></div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

// Escape HTML to prevent XSS
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag])
    );
}

// Handle Form Submission
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const prompt = promptInput.value.trim();
    if (!prompt) return;
    
    const capability = personaSelect.value;
    
    // Add User Message to UI and to shared history
    appendMessage('user', prompt);
    conversationHistory.push({ role: 'user', content: prompt });
    
    // Reset Input
    promptInput.value = '';
    promptInput.style.height = 'auto';
    sendBtn.disabled = true;
    
    // Add Typng Indicator
    appendTypingIndicator();
    
    // Create an AbortController to explicitly set a 5-minute timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes
    
    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                capability: capability,
                messages: conversationHistory
            }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        removeTypingIndicator();
        
        if (!response.ok) {
            appendMessage('system', `Error: ${response.status} ${response.statusText}`);
            return;
        }
        
        const data = await response.json();
        
        if (data.choices && data.choices.length > 0) {
            const reply = data.choices[0].message.content;
            // Add assistant reply to shared history so next model knows what was said
            conversationHistory.push({ role: 'assistant', content: reply });
            appendMessage('system', reply);
        } else {
            appendMessage('system', "Error: No response generated.");
        }
        
    } catch (error) {
        removeTypingIndicator();
        appendMessage('system', `Connection Error: Make sure Uvicorn is running on port 8000.\n\nDetails: ${error.message}`);
    } finally {
        sendBtn.disabled = false;
        promptInput.focus();
    }
});

// Initialize UI
personaSelect.dispatchEvent(new Event('change'));
