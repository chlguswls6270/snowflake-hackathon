import ChatInput from "./components/ChatInput";

export default function Home() {
  return (
    <main className="h-[100dvh] w-screen overflow-hidden bg-slate-950 font-sans selection:bg-cyan-500/30">
      <ChatInput />
    </main>
  );
}
