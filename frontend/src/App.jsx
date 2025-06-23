import './index.css'; // Tailwind CSS
import ChatBox from './components/ChatBox';

function App() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10 bg-gradient-to-br from-[#0f1117] to-[#1a1f2e] text-white">
      <div className="w-full max-w-3xl bg-white/10 backdrop-blur-md rounded-3xl shadow-2xl border border-white/20">
        <header className="py-6 border-b border-white/10">
          <h1 className="text-3xl sm:text-4xl font-bold text-center tracking-wide">
            AI Agent Chat
          </h1>
        </header>

        <main className="p-4 sm:p-6">
          <ChatBox />
        </main>
      </div>
    </div>
  );
}

export default App;
