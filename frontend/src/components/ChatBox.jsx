import React, { useState, useEffect, useRef } from 'react';

const generateId = () => Date.now().toString(36) + Math.random().toString(36).substring(2);

export default function ChatBox() {
  const [currentQuestion, setCurrentQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const currentAiMessageIdRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleInputChange = (e) => setCurrentQuestion(e.target.value);

  const handleSubmit = async (e) => {
    e.preventDefault();

    const trimmedQuestion = currentQuestion.trim();
    if (!trimmedQuestion) {
      setError('Please enter a question.');
      return;
    }

    setMessages((prev) => [...prev, { id: generateId(), sender: 'user', text: trimmedQuestion }]);
    setCurrentQuestion('');
    setIsLoading(true);
    setError(null);
    currentAiMessageIdRef.current = null;

    try {
      const response = await fetch('http://localhost:8000/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmedQuestion }),
      });

      if (!response.ok) throw new Error("Server responded with an error");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        if (chunk.startsWith("STREAM_ERROR:")) {
          setError(chunk.replace("STREAM_ERROR:", "").trim());
          setMessages((prev) => prev.filter((msg) => msg.id !== currentAiMessageIdRef.current));
          break;
        }

        setMessages((prevMessages) => {
          if (
            currentAiMessageIdRef.current &&
            prevMessages[prevMessages.length - 1]?.id === currentAiMessageIdRef.current
          ) {
            return prevMessages.map((msg) =>
              msg.id === currentAiMessageIdRef.current
                ? { ...msg, text: msg.text + chunk }
                : msg
            );
          } else {
            const newId = generateId() + '_ai';
            currentAiMessageIdRef.current = newId;
            return [...prevMessages, { id: newId, sender: 'ai', text: chunk }];
          }
        });
      }

    } catch (err) {
      console.error('Streaming error:', err);
      setError(err.message || 'Unexpected error occurred.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex flex-col h-screen">
      {/* Messages */}
      <div className="flex-grow overflow-y-auto p-4 space-y-3 scroll-smooth">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex items-start ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.sender === 'ai' && (
              <div className="w-8 h-8 mr-2 text-2xl">{'🤖'}</div>
            )}
            <div
              className={`max-w-[80%] py-2 px-4 rounded-2xl shadow-md break-words text-sm sm:text-base ${
                msg.sender === 'user'
                  ? 'bg-gray-100 text-gray-800 rounded-br-none'
                  : 'bg-white/10 backdrop-blur-sm text-white border border-white/30 rounded-bl-none'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
            </div>
            {msg.sender === 'user' && (
              <div className="w-8 h-8 ml-2 text-2xl">{'🧑\u200d💻'}</div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 mx-4 mb-2 bg-red-100 border border-red-300 text-red-600 rounded-lg text-sm flex-shrink-0">
          {error}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-white/20 flex-shrink-0">
        <div className="flex items-center gap-3 w-full max-w-4xl mx-auto">
          <input
            type="text"
            value={currentQuestion}
            onChange={handleInputChange}
            placeholder="Ask about weather or stocks..."
            className="flex-grow py-3 px-4 rounded-xl text-sm sm:text-base text-gray-800 bg-white placeholder-gray-500 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 shadow-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading}
            className="py-3 px-5 bg-sky-500 text-white rounded-xl hover:bg-sky-600 transition disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>Sending...</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <span>Search</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}