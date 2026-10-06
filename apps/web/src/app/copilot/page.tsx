"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { AIBadge } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { ErrorState, EmptyState, Skeleton } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type { CopilotConversation, CopilotConversationDetail, CopilotMessage, ReferencedEntity } from "@/lib/types";

const SUGGESTED_QUESTIONS = [
  "What needs my attention today?",
  "Which fields currently have risks?",
  "What recommendations do I have?",
  "Which activities are overdue?",
  "How are my crops progressing?",
  "Give me a summary of my farm.",
];

const ENTITY_LABEL: Record<ReferencedEntity["entity_type"], string> = {
  farm: "Farm",
  field: "Field",
  crop: "Crop",
  risk: "Risk",
  recommendation: "Recommendation",
  activity: "Activity",
};

let pendingIdCounter = 0;

function nextPendingId(): string {
  pendingIdCounter += 1;
  return `pending-${pendingIdCounter}`;
}

function ReferenceChips({ entities }: { entities: ReferencedEntity[] }) {
  if (entities.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {entities.map((e) => (
        <span
          key={`${e.entity_type}-${e.entity_id}`}
          className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs"
        >
          <span className="font-medium text-[var(--color-text-muted)]">{ENTITY_LABEL[e.entity_type]}</span>
          <span className="text-[var(--color-text-primary)]">{e.label}</span>
        </span>
      ))}
    </div>
  );
}

function MessageBubble({ message, index }: { message: CopilotMessage; index: number }) {
  const isAssistant = message.role === "ASSISTANT";
  return (
    <div className={`stagger-item flex ${isAssistant ? "justify-start" : "justify-end"}`} style={stagger(Math.min(index, 8))}>
      <div
        className={`max-w-[85%] rounded-[var(--radius-md)] px-4 py-3 text-sm shadow-[var(--shadow-sm)] transition-shadow duration-[var(--duration-normal)] ${
          isAssistant
            ? "border border-[var(--color-ai-accent)]/25 bg-[var(--color-ai-accent-soft)] text-[var(--color-text-primary)] shadow-[var(--shadow-glow-ai)]"
            : "bg-[var(--color-brand)] text-white"
        }`}
      >
        {isAssistant && (
          <div className="mb-1.5">
            <AIBadge label={message.is_mock ? "AgriMind Copilot · mock model" : "AgriMind Copilot"} />
          </div>
        )}
        <p className="whitespace-pre-line">{message.content}</p>
        {isAssistant && <ReferenceChips entities={message.referenced_entities} />}
        {isAssistant && message.context_freshness_warnings.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs text-[var(--color-status-monitoring)]">
            {message.context_freshness_warnings.map((w, i) => (
              <li key={i}>⚠ {w}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function CopilotPage() {
  const [conversations, setConversations] = useState<CopilotConversation[] | null>(null);
  const [activeConversation, setActiveConversation] = useState<CopilotConversationDetail | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);

  const threadEndRef = useRef<HTMLDivElement>(null);

  const loadConversations = () => {
    setIsLoadingList(true);
    setListError(null);
    api
      .get<CopilotConversation[]>("/copilot/conversations")
      .then(setConversations)
      .catch((err) => setListError(err instanceof ApiError ? err.message : "Could not load your conversations."))
      .finally(() => setIsLoadingList(false));
  };

  useEffect(loadConversations, []);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation?.messages.length]);

  const openConversation = (id: string) => {
    setIsLoadingDetail(true);
    setDetailError(null);
    api
      .get<CopilotConversationDetail>(`/copilot/conversations/${id}`)
      .then(setActiveConversation)
      .catch((err) => setDetailError(err instanceof ApiError ? err.message : "Could not load this conversation."))
      .finally(() => setIsLoadingDetail(false));
  };

  const startNewConversation = async () => {
    setDetailError(null);
    try {
      const conversation = await api.post<CopilotConversation>("/copilot/conversations", {});
      setActiveConversation({ ...conversation, messages: [] });
      setConversations((prev) => (prev ? [conversation, ...prev] : [conversation]));
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Could not start a new conversation.");
    }
  };

  const sendMessage = async (content: string) => {
    if (!content.trim()) return;

    let conversation = activeConversation;
    if (!conversation) {
      try {
        const created = await api.post<CopilotConversation>("/copilot/conversations", {});
        conversation = { ...created, messages: [] };
        setActiveConversation(conversation);
        setConversations((prev) => (prev ? [created, ...prev] : [created]));
      } catch (err) {
        setDetailError(err instanceof ApiError ? err.message : "Could not start a new conversation.");
        return;
      }
    }

    const userMessage: CopilotMessage = {
      id: nextPendingId(),
      role: "USER",
      content,
      provider_name: null,
      is_mock: null,
      referenced_entities: [],
      context_freshness_warnings: [],
      created_at: new Date().toISOString(),
    };
    setActiveConversation((prev) => (prev ? { ...prev, messages: [...prev.messages, userMessage] } : prev));
    setDraft("");
    setDetailError(null);
    setLastFailedMessage(null);
    setIsSending(true);

    try {
      const assistantMessage = await api.post<CopilotMessage>(`/copilot/conversations/${conversation.id}/messages`, { content });
      setActiveConversation((prev) => (prev ? { ...prev, messages: [...prev.messages, assistantMessage] } : prev));
      loadConversations();
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "Copilot is unavailable right now.");
      setLastFailedMessage(content);
      // Remove the optimistic user bubble that never got a reply, so retry doesn't duplicate it.
      setActiveConversation((prev) => (prev ? { ...prev, messages: prev.messages.filter((m) => m.id !== userMessage.id) } : prev));
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage(draft);
  };

  return (
    <AppShell>
      <AmbientBackground variant="copilot" />
      <div className="flex h-[calc(100vh-8rem)] gap-6 sm:h-[calc(100vh-4rem)]">
        {/* Conversation list */}
        <aside className="hidden w-64 shrink-0 flex-col gap-3 sm:flex">
          <Button size="sm" onClick={startNewConversation}>
            New conversation
          </Button>
          {listError && <ErrorState message={listError} onRetry={loadConversations} />}
          {isLoadingList && !listError && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10" />
              <Skeleton className="h-10" />
            </div>
          )}
          {conversations && conversations.length === 0 && !isLoadingList && (
            <p className="px-1 text-sm text-[var(--color-text-muted)]">No conversations yet.</p>
          )}
          {conversations && conversations.length > 0 && (
            <ul className="flex flex-col gap-1 overflow-y-auto">
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => openConversation(c.id)}
                    className={`relative w-full truncate rounded-[var(--radius-sm)] px-3 py-2 text-left text-sm transition-colors duration-[var(--duration-fast)] ${
                      activeConversation?.id === c.id
                        ? "bg-[var(--color-brand-soft)] text-[var(--color-brand-strong)]"
                        : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
                    }`}
                  >
                    {c.title || "New conversation"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Chat panel */}
        <section className="flex min-w-0 flex-1 flex-col rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-[var(--shadow-sm)]">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3 sm:hidden">
            <span className="text-sm font-medium text-[var(--color-text-primary)]">AgriMind Copilot</span>
            <Button size="sm" variant="secondary" onClick={startNewConversation}>
              New
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {isLoadingDetail && (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-12 w-2/3" />
                <Skeleton className="ml-auto h-8 w-1/2" />
              </div>
            )}

            {!isLoadingDetail && !activeConversation && (
              <div className="animate-in flex h-full flex-col items-center justify-center gap-4 text-center">
                <span aria-hidden className="text-3xl text-[var(--color-ai-accent-strong)]" style={{ animation: "pulseGlow 2.4s ease-in-out infinite" }}>✦</span>
                <EmptyState
                  title="Ask AgriMind Copilot about your farm"
                  description="Get grounded answers about your farms, fields, crops, risks, and recommendations -- based on your real data."
                />
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      className="rounded-full border border-[var(--color-border)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors duration-[var(--duration-fast)] hover:border-[var(--color-ai-accent)] hover:text-[var(--color-ai-accent-strong)]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!isLoadingDetail && activeConversation && (
              <div className="flex flex-col gap-3">
                {activeConversation.messages.length === 0 && (
                  <p className="text-center text-sm text-[var(--color-text-muted)]">Ask your first question below.</p>
                )}
                {activeConversation.messages.map((m, i) => (
                  <MessageBubble key={m.id} message={m} index={i} />
                ))}
                {isSending && (
                  <div className="animate-in flex items-center gap-2 rounded-[var(--radius-md)] border border-[var(--color-ai-accent)]/20 bg-[var(--color-ai-accent-soft)] px-4 py-3 text-sm text-[var(--color-ai-accent-strong)]">
                    <span className="thinking-dots" aria-hidden>
                      <span /><span /><span />
                    </span>
                    AgriMind Copilot is thinking…
                  </div>
                )}
                <div ref={threadEndRef} />
              </div>
            )}

            {detailError && (
              <div className="mt-4">
                <ErrorState
                  message={detailError}
                  onRetry={lastFailedMessage ? () => sendMessage(lastFailedMessage) : undefined}
                />
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2 border-t border-[var(--color-border)] p-3">
            <label htmlFor="copilot-input" className="sr-only">
              Ask AgriMind Copilot
            </label>
            <input
              id="copilot-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about your farm…"
              className="flex-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-[border-color,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-standard)] focus:border-[var(--color-ai-accent)] focus:shadow-[0_0_0_3px_var(--color-ai-accent-soft)]"
            />
            <Button type="submit" size="sm" isLoading={isSending} disabled={!draft.trim()}>
              Send
            </Button>
          </form>
        </section>
      </div>
    </AppShell>
  );
}
