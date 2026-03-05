import Sidebar from '../components/Sidebar';
import ChatInput from '../components/ChatInput';

export default function DashboardLayout({ children }) {

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0B0E14] font-sans transition-colors duration-500">
        <Sidebar /> {/* Sticky Sidebar */}
        
        <main className="flex-1 flex flex-col relative overflow-hidden">
          {/* Main Stage (Scrollable) */}
          <section className="flex-1 overflow-y-auto px-4 md:px-20 py-10">
            {children}
          </section>

          {/* Floating Input Dock*/}
          <div className="absolute bottom-0 left-0 w-full p-6 bg-gradient-to-t from-slate-50 dark:from-[#0B0E14]">
            <ChatInput />
          </div>
        </main>
      </div>
    );
}