import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  ChevronDown,
  Database,
  MessageSquare,
  Send,
  Sparkles,
  User,
  X,
} from 'lucide-react';
import { useDatasets } from '@/hooks/useDatasets';
import { aiApi } from '@/services/api';
import type { ChatMessage } from '@/types';
import { cn } from '@/utils/cn';
import { formatBytes, formatNumber } from '@/utils/format';

const SUGGESTED_QUESTIONS = [
  'What does this dataset contain?',
  'Which columns have the most missing values?',
  'What should I clean before training an ML model?',
  'Which numeric columns are highly skewed?',
  'Are there any potential target leakage risks?',
  'Which features should I consider dropping?',
  'Summarize the key statistics',
  'Are there any class imbalance issues?',
];

export default function AIChatPage() {
  const { data: datasetsPage, isLoading: datasetsLoading } = useDatasets(1, 100);
  const readyDatasets = (datasetsPage?.items ?? []).filter((d) => d.status === 'ready');

  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [showSelector, setShowSelector] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const selectedDataset = readyDatasets.find((d) => d.id === selectedDatasetId);

  const sendMessage = async (text: string) => {
    if (!text.trim() || !selectedDatasetId || isLoading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await aiApi.chat(selectedDatasetId, text, messages);
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      const errorMsg: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please make sure the AI service is available and try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  const switchDataset = (id: string) => {
    if (id !== selectedDatasetId) {
      setSelectedDatasetId(id);
      setMessages([]);
    }
    setShowSelector(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-purple-900/50 rounded-lg flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white">AI Chat</h1>
            <p className="text-xs text-gray-400">
              {selectedDataset
                ? `Analyzing: ${selectedDataset.name}`
                : 'Select a dataset to start chatting'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Dataset Selector */}
          <div className="relative">
            <button
              onClick={() => setShowSelector(!showSelector)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-colors border',
                selectedDatasetId
                  ? 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                  : 'bg-indigo-600 border-indigo-500 text-white hover:bg-indigo-500'
              )}
            >
              <Database className="w-4 h-4" />
              {selectedDataset ? selectedDataset.name : 'Select Dataset'}
              <ChevronDown className={cn('w-4 h-4 transition-transform', showSelector && 'rotate-180')} />
            </button>

            <AnimatePresence>
              {showSelector && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute right-0 top-full mt-2 w-80 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl z-50 overflow-hidden"
                >
                  <div className="p-3 border-b border-gray-800">
                    <p className="text-xs font-medium text-gray-400">Ready datasets</p>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {readyDatasets.length === 0 ? (
                      <div className="p-4 text-center text-sm text-gray-500">
                        No datasets available
                      </div>
                    ) : (
                      readyDatasets.map((dataset) => (
                        <button
                          key={dataset.id}
                          onClick={() => switchDataset(dataset.id)}
                          className={cn(
                            'w-full text-left p-3 hover:bg-gray-800 transition-colors flex items-center justify-between',
                            selectedDatasetId === dataset.id && 'bg-purple-900/20'
                          )}
                        >
                          <div className="min-w-0">
                            <p className="text-sm text-white truncate">{dataset.name}</p>
                            <p className="text-xs text-gray-400">
                              {formatBytes(dataset.file_size_bytes)} ·{' '}
                              {dataset.row_count ? `${formatNumber(dataset.row_count)} rows` : ''}
                            </p>
                          </div>
                          {selectedDatasetId === dataset.id && (
                            <span className="w-2 h-2 bg-purple-400 rounded-full flex-shrink-0 ml-2" />
                          )}
                        </button>
                      ))
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
              title="Clear chat"
            >
              <X className="w-4 h-4 text-gray-400" />
            </button>
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {!selectedDatasetId ? (
          /* No dataset selected */
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
              <div className="w-16 h-16 bg-purple-900/30 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Brain className="w-8 h-8 text-purple-400" />
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">AI Dataset Assistant</h2>
              <p className="text-gray-400 mb-6">
                Select a dataset to start a conversation. I'll use the actual profiling statistics to answer your questions — no guessing.
              </p>
              {!datasetsLoading && readyDatasets.length > 0 && (
                <div className="space-y-2">
                  {readyDatasets.slice(0, 3).map((dataset) => (
                    <button
                      key={dataset.id}
                      onClick={() => switchDataset(dataset.id)}
                      className="w-full text-left p-3 bg-gray-900 border border-gray-800 hover:border-purple-700/50 rounded-xl transition-colors flex items-center gap-3"
                    >
                      <Database className="w-4 h-4 text-gray-400" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white truncate">{dataset.name}</p>
                        <p className="text-xs text-gray-400">
                          {dataset.row_count ? `${formatNumber(dataset.row_count)} rows` : ''} ·{' '}
                          {dataset.column_count ? `${dataset.column_count} cols` : ''}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : messages.length === 0 ? (
          /* Empty chat — show suggestions */
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-lg">
              <div className="w-12 h-12 bg-purple-900/30 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-6 h-6 text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">
                What would you like to know?
              </h3>
              <p className="text-gray-400 mb-6 text-sm">
                Analyzing <span className="text-white font-medium">{selectedDataset?.name}</span>.
                Ask me anything about its structure, quality, or ML readiness.
              </p>
              <div className="grid grid-cols-2 gap-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="text-left text-sm p-3 bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-700 rounded-xl text-gray-300 hover:text-white transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* Messages */
          <div className="max-w-3xl mx-auto space-y-4">
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    'flex gap-3',
                    msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                  )}
                >
                  <div
                    className={cn(
                      'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
                      msg.role === 'user'
                        ? 'bg-indigo-600'
                        : 'bg-purple-900 border border-purple-700'
                    )}
                  >
                    {msg.role === 'user' ? (
                      <User className="w-4 h-4 text-white" />
                    ) : (
                      <Brain className="w-4 h-4 text-purple-400" />
                    )}
                  </div>
                  <div
                    className={cn(
                      'max-w-2xl rounded-2xl px-4 py-3 text-sm',
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-gray-900 text-gray-200 border border-gray-800'
                    )}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.timestamp && (
                      <p className={cn(
                        'text-[10px] mt-2',
                        msg.role === 'user' ? 'text-indigo-200/60' : 'text-gray-500'
                      )}>
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </p>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-3"
              >
                <div className="w-8 h-8 rounded-full bg-purple-900 border border-purple-700 flex items-center justify-center">
                  <Brain className="w-4 h-4 text-purple-400" />
                </div>
                <div className="bg-gray-900 border border-gray-800 rounded-2xl px-4 py-3">
                  <div className="flex gap-1.5">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        className="w-2 h-2 bg-purple-400 rounded-full"
                        animate={{ y: [0, -6, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      {selectedDatasetId && (
        <div className="px-6 py-4 border-t border-gray-800 bg-gray-900/50 backdrop-blur-sm">
          <form
            onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
            className="max-w-3xl mx-auto flex gap-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about your dataset..."
              disabled={isLoading}
              className="flex-1 px-5 py-3 bg-gray-800 border border-gray-700 rounded-xl text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 disabled:opacity-50 text-sm"
            />
            <motion.button
              type="submit"
              disabled={!input.trim() || isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="px-5 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
            >
              <Send className="w-5 h-5" />
            </motion.button>
          </form>
        </div>
      )}
    </div>
  );
}
