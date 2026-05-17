import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea } from '../components/ui/scroll-area';
import { Send, Upload, Menu, X, LayoutDashboard, CheckCircle2, Loader2, AlertTriangle, Sparkles, Plus } from 'lucide-react';
import { chat, createReport, getAudioJob, uploadAudio, type ConversationPhase } from '../lib/api';

type ChatMessage =
  | {
      kind: 'text';
      id: string;
      text: string;
      sender: 'user' | 'ai';
      timestamp: Date;
    }
  | {
      kind: 'uploadStatus';
      id: string;
      sender: 'user' | 'ai';
      timestamp: Date;
      status: 'uploading' | 'processing' | 'ready' | 'error';
    }
  | {
      kind: 'context';
      id: string;
      sender: 'user' | 'ai';
      timestamp: Date;
      context: string;
    };

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

interface Conversation {
  id: string;
  title: string;
  lastMessage: Date;
}

type StoredMessage = Omit<Message, 'timestamp'> & { timestamp: number };
type StoredConversation = Omit<Conversation, 'lastMessage'> & { lastMessage: number };

type StoredChatStateV1 = {
  v: 1;
  messages: StoredMessage[];
  conversations: StoredConversation[];
  currentConversationId: string;
  userContext: string;
  activeAudioId: string | null;
  backendConversationId: string | null;
};

type StoredChatMessageV2 =
  | { kind: 'text'; id: string; sender: 'user' | 'ai'; timestamp: number; text: string }
  | {
      kind: 'uploadStatus';
      id: string;
      sender: 'user' | 'ai';
      timestamp: number;
      status: 'uploading' | 'processing' | 'ready' | 'error' | 'uploaded';
    }
  | { kind: 'context'; id: string; sender: 'user' | 'ai'; timestamp: number; context: string };

type StoredChatStateV2 = {
  v: 2;
  messages: StoredChatMessageV2[];
  conversations: StoredConversation[];
  currentConversationId: string;
  userContext: string;
  activeAudioId: string | null;
  backendConversationId: string | null;
};

type StoredConversationStateV3 = {
  messages: StoredChatMessageV2[];
  userContext: string;
  activeAudioId: string | null;
  backendConversationId: string | null;
  uploadError?: string | null;
  phase?: ConversationPhase;
  alignedFocus?: string | null;
};

type StoredChatStateV3 = {
  v: 3;
  conversations: StoredConversation[];
  currentConversationId: string;
  byId: Record<string, StoredConversationStateV3>;
};

const CHAT_STATE_KEY_V3 = 'guidepost.chatState.v3';
const CHAT_STATE_KEY_V2 = 'guidepost.chatState.v2';
const CHAT_STATE_KEY_V1 = 'guidepost.chatState.v1';

const initialMessages = (): ChatMessage[] => [];

const toChatMessage = (m: any): ChatMessage => {
  const ts = new Date(Number(m.timestamp) || Date.now());
  const sender = m.sender === 'ai' ? 'ai' : 'user';
  if (m.kind === 'uploadStatus') {
    const status =
      m.status === 'ready'
        ? 'ready'
        : m.status === 'processing'
          ? 'processing'
          : m.status === 'uploaded'
            ? 'processing'
            : m.status === 'error'
              ? 'error'
              : 'uploading';
    return { kind: 'uploadStatus', id: String(m.id), sender, timestamp: ts, status } as ChatMessage;
  }
  if (m.kind === 'context') {
    return { kind: 'context', id: String(m.id), sender, timestamp: ts, context: String(m.context ?? '') } as ChatMessage;
  }
  return { kind: 'text', id: String(m.id), sender, timestamp: ts, text: String(m.text ?? '') } as ChatMessage;
};

const toStoredChatMessageV2 = (m: ChatMessage): StoredChatMessageV2 => {
  if (m.kind === 'uploadStatus') {
    return {
      kind: 'uploadStatus',
      id: m.id,
      sender: m.sender,
      timestamp: m.timestamp.getTime(),
      status: m.status,
    };
  }
  if (m.kind === 'context') {
    return {
      kind: 'context',
      id: m.id,
      sender: m.sender,
      timestamp: m.timestamp.getTime(),
      context: m.context,
    };
  }
  return {
    kind: 'text',
    id: m.id,
    sender: m.sender,
    timestamp: m.timestamp.getTime(),
    text: m.text,
  };
};

const _truncateTitle = (s: string, max = 34) => {
  const oneLine = String(s || '').replace(/\s+/g, ' ').trim();
  if (!oneLine) return '';
  return oneLine.length > max ? `${oneLine.slice(0, max - 1)}…` : oneLine;
};

const suggestConversationTitle = (opts: {
  existingTitle: string;
  messages: ChatMessage[];
  fileName?: string;
}) => {
  const existing = (opts.existingTitle || '').trim();
  if (existing && existing !== 'New Conversation') return existing;

  if (opts.fileName) {
    const base = opts.fileName.replace(/\.[^.]+$/, '');
    const t = _truncateTitle(base, 38);
    if (t) return t;
  }

  const firstUserText = opts.messages.find((m) => m.kind === 'text' && m.sender === 'user') as
    | Extract<ChatMessage, { kind: 'text' }>
    | undefined;
  if (firstUserText?.text) return _truncateTitle(firstUserText.text, 38) || 'Conversation';

  return 'New Conversation';
};

export default function Chat() {
  const [messagesByConversationId, setMessagesByConversationId] = useState<Record<string, ChatMessage[]>>({
    '1': initialMessages(),
  });
  const [inputValue, setInputValue] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: '1',
      title: 'New Conversation',
      lastMessage: new Date(),
    },
  ]);
  const [currentConversationId, setCurrentConversationId] = useState('1');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isUploadingAudio, setIsUploadingAudio] = useState(false);
  const [uploadErrorByConversationId, setUploadErrorByConversationId] = useState<Record<string, string | null>>({
    '1': null,
  });
  const [userContextByConversationId, setUserContextByConversationId] = useState<Record<string, string>>({ '1': '' });
  const [activeAudioIdByConversationId, setActiveAudioIdByConversationId] = useState<Record<string, string | null>>({
    '1': null,
  });
  const [backendConversationIdByConversationId, setBackendConversationIdByConversationId] = useState<
    Record<string, string | null>
  >({ '1': null });
  const [phaseByConversationId, setPhaseByConversationId] = useState<
    Record<string, ConversationPhase>
  >({ '1': 'coaching' });
  const [alignedFocusByConversationId, setAlignedFocusByConversationId] = useState<
    Record<string, string | null>
  >({ '1': null });
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const didRestoreRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const userName = localStorage.getItem('userName') || 'there';

  const messages = messagesByConversationId[currentConversationId] ?? initialMessages();
  const userContext = userContextByConversationId[currentConversationId] ?? '';
  const activeAudioId = activeAudioIdByConversationId[currentConversationId] ?? null;
  const backendConversationId = backendConversationIdByConversationId[currentConversationId] ?? null;
  const uploadError = uploadErrorByConversationId[currentConversationId] ?? null;
  const currentPhase = phaseByConversationId[currentConversationId] ?? 'coaching';
  const alignedFocus = alignedFocusByConversationId[currentConversationId] ?? null;

  useEffect(() => {
    if (didRestoreRef.current) return;
    didRestoreRef.current = true;

    try {
      const rawV3 = localStorage.getItem(CHAT_STATE_KEY_V3);
      const rawV2 = localStorage.getItem(CHAT_STATE_KEY_V2);
      const rawV1 = localStorage.getItem(CHAT_STATE_KEY_V1);
      const raw = rawV3 || rawV2 || rawV1;
      if (!raw) return;
      const parsed: any = JSON.parse(raw);

      if (parsed.v === 3) {
        const byId = typeof parsed.byId === 'object' && parsed.byId ? parsed.byId : {};

        const restoredConversations: Conversation[] =
          Array.isArray(parsed.conversations) && parsed.conversations.length > 0
            ? parsed.conversations.map((c: any) => ({
                id: String(c?.id ?? ''),
                title: String(c?.title ?? 'Conversation'),
                lastMessage: new Date(Number(c?.lastMessage) || Date.now()),
              }))
            : [{ id: '1', title: 'New Conversation', lastMessage: new Date() }];

        const restoredCurrentId =
          typeof parsed.currentConversationId === 'string' && parsed.currentConversationId
            ? parsed.currentConversationId
            : restoredConversations[0]?.id || '1';

        const nextMessagesById: Record<string, ChatMessage[]> = {};
        const nextUserContextById: Record<string, string> = {};
        const nextActiveAudioIdById: Record<string, string | null> = {};
        const nextBackendConversationIdById: Record<string, string | null> = {};
        const nextUploadErrorById: Record<string, string | null> = {};
        const nextPhaseById: Record<string, ConversationPhase> = {};
        const nextAlignedFocusById: Record<string, string | null> = {};

        for (const c of restoredConversations) {
          const st = byId[String(c.id)] || {};
          const rawMsgs = Array.isArray(st.messages) ? st.messages : [];
          nextMessagesById[c.id] = rawMsgs.length > 0 ? rawMsgs.map(toChatMessage) : initialMessages();
          nextUserContextById[c.id] = typeof st.userContext === 'string' ? st.userContext : '';
          nextActiveAudioIdById[c.id] = typeof st.activeAudioId === 'string' ? st.activeAudioId : null;
          nextBackendConversationIdById[c.id] =
            typeof st.backendConversationId === 'string' ? st.backendConversationId : null;
          nextUploadErrorById[c.id] = typeof st.uploadError === 'string' ? st.uploadError : null;
          nextPhaseById[c.id] = st.phase === 'alignment' ? 'alignment' : 'coaching';
          nextAlignedFocusById[c.id] = typeof st.alignedFocus === 'string' ? st.alignedFocus : null;
        }

        setConversations(restoredConversations);
        setCurrentConversationId(restoredCurrentId);
        setMessagesByConversationId(nextMessagesById);
        setUserContextByConversationId(nextUserContextById);
        setActiveAudioIdByConversationId(nextActiveAudioIdById);
        setBackendConversationIdByConversationId(nextBackendConversationIdById);
        setUploadErrorByConversationId(nextUploadErrorById);
        setPhaseByConversationId(nextPhaseById);
        setAlignedFocusByConversationId(nextAlignedFocusById);
        return;
      }

      // Migrate v1/v2 (single message list) into v3 by assigning it to the current conversation only.
      const restoredConversations: Conversation[] =
        Array.isArray(parsed.conversations) && parsed.conversations.length > 0
          ? parsed.conversations.map((c: any) => ({
              id: String((c as any).id),
              title: String((c as any).title ?? 'Conversation'),
              lastMessage: new Date(Number((c as any).lastMessage) || Date.now()),
            }))
          : [{ id: '1', title: 'New Conversation', lastMessage: new Date() }];

      const restoredCurrentId =
        typeof parsed.currentConversationId === 'string' && parsed.currentConversationId
          ? parsed.currentConversationId
          : restoredConversations[0]?.id || '1';

      const migratedMessages =
        parsed.v === 2 && Array.isArray(parsed.messages)
          ? parsed.messages.map(toChatMessage)
          : parsed.v === 1 && Array.isArray(parsed.messages)
            ? parsed.messages.map((m: any) => ({
                kind: 'text',
                id: String(m.id),
                text: String(m.text ?? ''),
                sender: m.sender === 'ai' ? 'ai' : 'user',
                timestamp: new Date(Number(m.timestamp) || Date.now()),
              }))
            : [];

      const nextMessagesById: Record<string, ChatMessage[]> = {};
      const nextUserContextById: Record<string, string> = {};
      const nextActiveAudioIdById: Record<string, string | null> = {};
      const nextBackendConversationIdById: Record<string, string | null> = {};
      const nextUploadErrorById: Record<string, string | null> = {};

      for (const c of restoredConversations) {
        nextMessagesById[c.id] = c.id === restoredCurrentId && migratedMessages.length > 0 ? migratedMessages : initialMessages();
        nextUserContextById[c.id] =
          c.id === restoredCurrentId && typeof parsed.userContext === 'string' ? parsed.userContext : '';
        nextActiveAudioIdById[c.id] =
          c.id === restoredCurrentId && typeof parsed.activeAudioId === 'string' ? parsed.activeAudioId : null;
        nextBackendConversationIdById[c.id] =
          c.id === restoredCurrentId && typeof parsed.backendConversationId === 'string' ? parsed.backendConversationId : null;
        nextUploadErrorById[c.id] = null;
      }

      setConversations(restoredConversations);
      setCurrentConversationId(restoredCurrentId);
      setMessagesByConversationId(nextMessagesById);
      setUserContextByConversationId(nextUserContextById);
      setActiveAudioIdByConversationId(nextActiveAudioIdById);
      setBackendConversationIdByConversationId(nextBackendConversationIdById);
      setUploadErrorByConversationId(nextUploadErrorById);
    } catch {
      // Ignore corrupt state.
    }
  }, []);

  useEffect(() => {
    if (!didRestoreRef.current) return;
    try {
      const byId: Record<string, StoredConversationStateV3> = {};
      for (const c of conversations) {
        const id = c.id;
        byId[id] = {
          messages: (messagesByConversationId[id] ?? initialMessages()).map(toStoredChatMessageV2),
          userContext: userContextByConversationId[id] ?? '',
          activeAudioId: activeAudioIdByConversationId[id] ?? null,
          backendConversationId: backendConversationIdByConversationId[id] ?? null,
          uploadError: uploadErrorByConversationId[id] ?? null,
          phase: phaseByConversationId[id] ?? 'coaching',
          alignedFocus: alignedFocusByConversationId[id] ?? null,
        };
      }

      const state: StoredChatStateV3 = {
        v: 3,
        conversations: conversations.map((c) => ({
          id: c.id,
          title: c.title,
          lastMessage: c.lastMessage.getTime(),
        })),
        currentConversationId,
        byId,
      };
      localStorage.setItem(CHAT_STATE_KEY_V3, JSON.stringify(state));
    } catch {
      // Ignore quota/security errors.
    }
  }, [
    messagesByConversationId,
    conversations,
    currentConversationId,
    userContextByConversationId,
    activeAudioIdByConversationId,
    backendConversationIdByConversationId,
    uploadErrorByConversationId,
    phaseByConversationId,
    alignedFocusByConversationId,
  ]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversationId, messages, isSending]);

  const generateReportWithFocus = async (convId: string, audioId: string, focus: string) => {
    setIsGeneratingReport(true);
    const targetName = localStorage.getItem('userName') || undefined;
    try {
      const reportRes = await createReport({
        audioId,
        targetName,
        alignedFocus: focus,
      });
      const analysisText = (reportRes.report || '').trim() || '(no analysis)';
      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: `${Date.now()}-report`,
              text: `Here's your focused coaching report:\n\n${analysisText}`,
              sender: 'ai',
              timestamp: new Date(),
            },
            {
              kind: 'text',
              id: `${Date.now()}-coaching-ready`,
              text: "Let's dig into this. What stands out to you, or where would you like to start?",
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Report generation failed.';
      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: `${Date.now()}-report-err`,
              text: `I couldn't generate the report. ${msg} We can still chat about the conversation.`,
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const skipAlignment = async () => {
    const convId = currentConversationId;
    const audioId = activeAudioIdByConversationId[convId] ?? null;
    if (!audioId) return;

    const fallbackFocus = 'General interpersonal improvement';

    setPhaseByConversationId((prev) => ({ ...prev, [convId]: 'coaching' }));
    setAlignedFocusByConversationId((prev) => ({ ...prev, [convId]: fallbackFocus }));

    setMessagesByConversationId((prev) => {
      const existing = prev[convId] ?? initialMessages();
      return {
        ...prev,
        [convId]: [
          ...existing,
          {
            kind: 'text',
            id: `${Date.now()}-skip`,
            text: 'Generating your report now...',
            sender: 'ai',
            timestamp: new Date(),
          },
        ],
      };
    });

    await generateReportWithFocus(convId, audioId, fallbackFocus);
  };

  const handleGenerateReport = async () => {
    const convId = currentConversationId;
    const audioId = activeAudioIdByConversationId[convId] ?? null;
    const focus = (alignedFocusByConversationId[convId] ?? '').trim() || 'General interpersonal improvement';
    if (!audioId || isGeneratingReport) return;
    await generateReportWithFocus(convId, audioId, focus);
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;
    const convId = currentConversationId;
    const text = inputValue;
    const phase = phaseByConversationId[convId] ?? 'coaching';

    const newMessage: ChatMessage = {
      kind: 'text',
      id: Date.now().toString(),
      text,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessagesByConversationId((prev) => {
      const existing = prev[convId] ?? initialMessages();
      return { ...prev, [convId]: [...existing, newMessage] };
    });
    setInputValue('');

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== convId) return c;
        const nextTitle = suggestConversationTitle({
          existingTitle: c.title,
          messages: (messagesByConversationId[convId] ?? []).concat([newMessage]),
        });
        return { ...c, lastMessage: new Date(), title: nextTitle };
      })
    );

    const audioId = activeAudioIdByConversationId[convId] ?? null;
    if (!audioId) {
      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: `${Date.now()}-no-audio`,
              text: 'To get started, upload a recording of a conversation using the button on the left.',
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });
      return;
    }

    setIsSending(true);
    try {
      const res = await chat({
        audioId,
        conversationId: (backendConversationIdByConversationId[convId] ?? null) || undefined,
        message: newMessage.text,
        phase,
      });
      if (res.conversationId) {
        setBackendConversationIdByConversationId((prev) => ({ ...prev, [convId]: res.conversationId ?? null }));
      }

      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: (Date.now() + 1).toString(),
              text: res.reply,
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });

      if (phase === 'alignment' && res.alignedFocus) {
        setAlignedFocusByConversationId((prev) => ({ ...prev, [convId]: res.alignedFocus! }));
        setPhaseByConversationId((prev) => ({ ...prev, [convId]: 'coaching' }));

        const focus = res.alignedFocus;
        const aid = activeAudioIdByConversationId[convId] ?? null;
        if (aid) {
          setMessagesByConversationId((prev) => {
            const existing = prev[convId] ?? initialMessages();
            return {
              ...prev,
              [convId]: [
                ...existing,
                {
                  kind: 'text',
                  id: `${Date.now()}-generating`,
                  text: 'Putting together your insights — this takes about 15–30 seconds...',
                  sender: 'ai',
                  timestamp: new Date(),
                },
              ],
            };
          });
          generateReportWithFocus(convId, aid, focus);
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Chat request failed.';
      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: `${Date.now()}-chat-err`,
              text: `I couldn’t reach the chat service. ${msg}`,
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const convId = currentConversationId;

    setUploadErrorByConversationId((prev) => ({ ...prev, [convId]: null }));
    setIsUploadingAudio(true);
    setActiveAudioIdByConversationId((prev) => ({ ...prev, [convId]: null }));
    setBackendConversationIdByConversationId((prev) => ({ ...prev, [convId]: null }));

    const uploadStatusId = `${Date.now()}-upload`;
    const userMsg: ChatMessage = {
      kind: 'uploadStatus',
      id: uploadStatusId,
      sender: 'user',
      timestamp: new Date(),
      status: 'uploading',
    };

    setMessagesByConversationId((prev) => {
      const existing = prev[convId] ?? initialMessages();
      return { ...prev, [convId]: [...existing, userMsg] };
    });

    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== convId) return c;
        const nextTitle = suggestConversationTitle({
          existingTitle: c.title,
          messages: messagesByConversationId[convId] ?? [],
          fileName: file.name,
        });
        return { ...c, lastMessage: new Date(), title: nextTitle };
      })
    );

    try {
      const targetName = localStorage.getItem('userName') || undefined;
      const userEmail = localStorage.getItem('userEmail') || undefined;
      const userId = localStorage.getItem('userId') || undefined;
      const { audioId } = await uploadAudio({
        file,
        targetName,
        userEmail,
        userId,
      });

      // Upload is complete; diarization/report processing begins.
      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: existing.map((m) =>
            m.kind === 'uploadStatus' && m.id === uploadStatusId ? { ...m, status: 'processing' } : m
          ),
        };
      });

      // Poll until processed
      for (let i = 0; i < 180; i++) {
        const job = await getAudioJob(audioId);

        if (job.status === 'uploaded' || job.status === 'processing') {
          setMessagesByConversationId((prev) => {
            const existing = prev[convId] ?? initialMessages();
            return {
              ...prev,
              [convId]: existing.map((m) =>
                m.kind === 'uploadStatus' && m.id === uploadStatusId ? { ...m, status: 'processing' } : m
              ),
            };
          });
        }

        if (job.status === 'ready') {
          setActiveAudioIdByConversationId((prev) => ({ ...prev, [convId]: audioId }));

          setMessagesByConversationId((prev) => {
            const existing = prev[convId] ?? initialMessages();
            return {
              ...prev,
              [convId]: existing.map((m) =>
                m.kind === 'uploadStatus' && m.id === uploadStatusId ? { ...m, status: 'ready' } : m
              ),
            };
          });

          // Enter alignment phase — ask the coach to propose focus areas
          setPhaseByConversationId((prev) => ({ ...prev, [convId]: 'alignment' }));

          try {
            const alignRes = await chat({
              audioId,
              conversationId: (backendConversationIdByConversationId[convId] ?? null) || undefined,
              message: 'I just uploaded a conversation.',
              phase: 'alignment',
            });
            if (alignRes.conversationId) {
              setBackendConversationIdByConversationId((prev) => ({
                ...prev,
                [convId]: alignRes.conversationId ?? null,
              }));
            }

            setMessagesByConversationId((prev) => {
              const existing = prev[convId] ?? initialMessages();
              return {
                ...prev,
                [convId]: [
                  ...existing,
                  {
                    kind: 'text',
                    id: `${Date.now()}-align-intro`,
                    text: alignRes.reply,
                    sender: 'ai',
                    timestamp: new Date(),
                  },
                ],
              };
            });

            if (alignRes.alignedFocus) {
              setAlignedFocusByConversationId((prev) => ({ ...prev, [convId]: alignRes.alignedFocus! }));
              setPhaseByConversationId((prev) => ({ ...prev, [convId]: 'coaching' }));
              setMessagesByConversationId((prev) => {
                const existing = prev[convId] ?? initialMessages();
                return {
                  ...prev,
                  [convId]: [
                    ...existing,
                    {
                      kind: 'text',
                      id: `${Date.now()}-generating`,
                      text: 'Putting together your insights — this takes about 15–30 seconds...',
                      sender: 'ai',
                      timestamp: new Date(),
                    },
                  ],
                };
              });
              generateReportWithFocus(convId, audioId, alignRes.alignedFocus);
            }
          } catch {
            setMessagesByConversationId((prev) => {
              const existing = prev[convId] ?? initialMessages();
              return {
                ...prev,
                [convId]: [
                  ...existing,
                  {
                    kind: 'text',
                    id: `${Date.now()}-align-err`,
                    text: "I've processed your conversation. What would you like to focus on?",
                    sender: 'ai',
                    timestamp: new Date(),
                  },
                ],
              };
            });
          }

          setConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              const nextTitle = suggestConversationTitle({
                existingTitle: c.title,
                messages: (messagesByConversationId[convId] ?? []).concat([]),
                fileName: file.name,
              });
              return { ...c, lastMessage: new Date(), title: nextTitle };
            })
          );
          break;
        }

        if (job.status === 'error') {
          const msg = job.errorMessage || 'Audio processing failed.';
          throw new Error(msg);
        }

        // uploaded | processing
        await new Promise((r) => setTimeout(r, 2000));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setUploadErrorByConversationId((prev) => ({ ...prev, [convId]: msg }));

      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: existing.map((m) =>
            m.kind === 'uploadStatus' && m.id === uploadStatusId ? { ...m, status: 'error' } : m
          ),
        };
      });

      setMessagesByConversationId((prev) => {
        const existing = prev[convId] ?? initialMessages();
        return {
          ...prev,
          [convId]: [
            ...existing,
            {
              kind: 'text',
              id: `${Date.now()}-err`,
              text: `I couldn’t process that file. ${msg}`,
              sender: 'ai',
              timestamp: new Date(),
            },
          ],
        };
      });
    } finally {
      setIsUploadingAudio(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const startNewConversation = () => {
    const newConv: Conversation = {
      id: Date.now().toString(),
      title: 'New Conversation',
      lastMessage: new Date(),
    };
    setConversations([newConv, ...conversations]);
    setCurrentConversationId(newConv.id);
    setUserContextByConversationId((prev) => ({ ...prev, [newConv.id]: '' }));
    setActiveAudioIdByConversationId((prev) => ({ ...prev, [newConv.id]: null }));
    setBackendConversationIdByConversationId((prev) => ({ ...prev, [newConv.id]: null }));
    setUploadErrorByConversationId((prev) => ({ ...prev, [newConv.id]: null }));
    setPhaseByConversationId((prev) => ({ ...prev, [newConv.id]: 'coaching' }));
    setAlignedFocusByConversationId((prev) => ({ ...prev, [newConv.id]: null }));
    setMessagesByConversationId((prev) => ({ ...prev, [newConv.id]: initialMessages() }));
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
      {/* Sidebar */}
      <div
        className={`${
          isSidebarOpen ? 'w-80' : 'w-0'
        } transition-all duration-300 border-r border-slate-200 flex min-h-0 flex-col overflow-hidden bg-white/80 backdrop-blur-lg`}
      >
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
              Guidepost
            </h1>
          </div>
          <div className="space-y-2">
            <Button
              onClick={() => navigate('/dashboard')}
              variant="ghost"
              className="w-full justify-start rounded-xl hover:bg-indigo-50 hover:text-indigo-600"
            >
              <LayoutDashboard className="w-4 h-4 mr-2" />
              Dashboard
            </Button>
            <Button
              onClick={startNewConversation}
              className="w-full rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Conversation
            </Button>
          </div>
        </div>

        <ScrollArea className="flex-1 min-h-0">
          <div className="p-3 space-y-2">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setCurrentConversationId(conv.id)}
                className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                  currentConversationId === conv.id
                    ? 'bg-gradient-to-r from-indigo-50 to-purple-50 shadow-md border-2 border-indigo-200'
                    : 'hover:bg-slate-50 border-2 border-transparent'
                }`}
              >
                <div className="font-semibold text-sm truncate text-slate-900">{conv.title}</div>
                <div className="text-xs text-slate-500 mt-1">
                  {conv.lastMessage.toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        </ScrollArea>

        <div className="p-6 border-t border-slate-200 bg-gradient-to-br from-slate-50 to-indigo-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center text-white font-bold">
              {userName.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-slate-900 truncate">{userName}</div>
              <div className="text-xs text-slate-600 truncate">{localStorage.getItem('userEmail')}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex min-h-0 flex-col">
        {/* Header */}
        <div className="h-16 border-b border-slate-200 flex items-center px-6 bg-white/70 backdrop-blur-lg">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="mr-4 rounded-xl hover:bg-indigo-50 hover:text-indigo-600"
          >
            {isSidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </Button>
          <h2 className="font-semibold text-slate-900">Personalized Assistant</h2>
          <div className="ml-auto flex items-center gap-2">
            {currentPhase === 'alignment' && (
              <>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                  Establishing focus...
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={skipAlignment}
                  className="text-xs text-slate-500 hover:text-slate-700 rounded-lg"
                  disabled={isSending || isGeneratingReport}
                >
                  Skip — just generate report
                </Button>
              </>
            )}
            {activeAudioId && (
              <>
                {currentPhase === 'coaching' && alignedFocus && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200 max-w-xs truncate">
                    <CheckCircle2 className="w-3 h-3 shrink-0" />
                    Focus: {alignedFocus}
                  </span>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGenerateReport}
                  disabled={isGeneratingReport || isSending}
                  className="text-xs rounded-lg border-indigo-200 text-indigo-700 hover:bg-indigo-50"
                >
                  Generate report
                </Button>
              </>
            )}
            {isGeneratingReport && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 border border-indigo-200">
                <Loader2 className="w-3 h-3 animate-spin" />
                Generating report...
              </span>
            )}
            {isSending && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                <Loader2 className="w-3 h-3 animate-spin" />
                Getting response...
              </span>
            )}
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1 min-h-0 p-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-24 text-center">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center mb-5 shadow-sm">
                  <Sparkles className="w-7 h-7 text-indigo-600" />
                </div>
                <h2 className="text-xl font-semibold text-slate-900 mb-2">
                  Hi {userName}, welcome to Guidepost
                </h2>
                <p className="text-sm text-slate-500 max-w-md mb-6 leading-relaxed">
                  Upload a conversation and we'll uncover the gap between
                  intention and impact.
                </p>
                <Button
                  onClick={handleFileUpload}
                  disabled={isUploadingAudio}
                  className="rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200 px-6 py-2.5 text-sm font-medium"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Upload audio
                </Button>
              </div>
            )}
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[70%] rounded-2xl px-4 py-3 shadow-sm ${
                    message.sender === 'user'
                      ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-indigo-200'
                      : 'bg-white/90 backdrop-blur text-slate-900 border border-slate-200'
                  }`}
                >
                  {message.kind === 'uploadStatus' ? (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        {message.status === 'uploading' || message.status === 'processing' ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : message.status === 'ready' ? (
                          <CheckCircle2 className="w-4 h-4" />
                        ) : (
                          <AlertTriangle className="w-4 h-4" />
                        )}
                        <div className="text-sm font-medium">
                          {message.status === 'uploading'
                            ? 'Uploading audio…'
                            : message.status === 'processing'
                              ? 'Processing (diarizing)…'
                              : message.status === 'ready'
                                ? 'Complete'
                                : 'Failed'}
                        </div>
                      </div>
                      <div
                        className={`w-full h-2 rounded-full ${
                          message.sender === 'user' ? 'bg-white/20' : 'bg-slate-200'
                        }`}
                      >
                        <div
                          className={`h-2 rounded-full ${
                            message.status === 'ready'
                              ? message.sender === 'user'
                                ? 'bg-white'
                                : 'bg-indigo-600'
                              : message.status === 'error'
                                ? message.sender === 'user'
                                  ? 'bg-red-300'
                                  : 'bg-red-500'
                                : message.sender === 'user'
                                  ? 'bg-white/60'
                                  : 'bg-indigo-400'
                          }`}
                          style={{
                            width:
                              message.status === 'uploading'
                                ? '35%'
                                : message.status === 'processing'
                                  ? '75%'
                                  : message.status === 'ready'
                                    ? '100%'
                                    : '100%',
                          }}
                        />
                      </div>
                    </div>
                  ) : message.kind === 'context' ? (
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide opacity-80 mb-1">
                        Context
                      </div>
                      <p className="whitespace-pre-wrap">{message.context}</p>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.text}</p>
                  )}
                  <div
                    className={`text-xs mt-1 ${
                      message.sender === 'user' ? 'text-indigo-100' : 'text-slate-500'
                    }`}
                  >
                    {message.timestamp.toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
            ))}
            {isSending && (
              <div className="flex justify-start">
                <div className="max-w-[70%] rounded-2xl px-4 py-3 shadow-sm bg-white/90 backdrop-blur text-slate-900 border border-slate-200">
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                    <span className="text-sm text-slate-600">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="border-t border-slate-200 p-4 bg-white/70 backdrop-blur-lg">
          <div className="max-w-3xl mx-auto">
            {uploadError && (
              <div className="mb-3 text-sm text-red-600">{uploadError}</div>
            )}
            {/* Context is now gathered conversationally during the alignment phase */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={handleFileUpload}
                className="shrink-0 rounded-xl border-slate-200 hover:border-indigo-200 hover:bg-indigo-50"
                disabled={isUploadingAudio}
              >
                <Upload className="w-4 h-4" />
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileChange}
                className="hidden"
              />
              <Textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Type your message..."
                rows={1}
                className="resize-none min-h-[40px] max-h-[120px] rounded-xl border-slate-200 focus:border-indigo-500 focus:ring-indigo-500"
              />
              <Button
                onClick={handleSendMessage}
                size="icon"
                className="shrink-0 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 shadow-lg shadow-indigo-200"
                disabled={isSending || isUploadingAudio || isGeneratingReport}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-xs text-slate-500 mt-2 text-center">
              Press Enter to send, Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}