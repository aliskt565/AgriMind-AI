import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CopilotPage from "../page";
import { api, ApiError } from "@/lib/api";

jest.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return { ...actual, api: { get: jest.fn(), post: jest.fn() } };
});

const mockedApi = api as jest.Mocked<typeof api>;

const CONVERSATION_1 = { id: "conv-1", title: "How are my crops doing?", created_at: "2026-08-12T09:00:00Z", updated_at: "2026-08-12T09:00:00Z" };

describe("CopilotPage", () => {
  beforeEach(() => {
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
  });

  it("shows the empty state with suggested questions when there is no active conversation", async () => {
    mockedApi.get.mockResolvedValue([]);
    render(<CopilotPage />);

    expect(await screen.findByText(/ask agrimind copilot about your farm/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /give me a summary of my farm/i })).toBeInTheDocument();
  });

  it("shows an error state with retry when the conversation list fails to load", async () => {
    mockedApi.get.mockRejectedValue(new ApiError(500, "internal_error", "Could not load your conversations."));
    render(<CopilotPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your conversations.");
  });

  it("lists existing conversations and opens one on click", async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/copilot/conversations") return Promise.resolve([CONVERSATION_1]);
      if (path === "/copilot/conversations/conv-1") {
        return Promise.resolve({
          ...CONVERSATION_1,
          messages: [
            { id: "m1", role: "USER", content: "How are my crops doing?", provider_name: null, is_mock: null, referenced_entities: [], context_freshness_warnings: [], created_at: "2026-08-12T09:00:00Z" },
            { id: "m2", role: "ASSISTANT", content: "Here's how your crops are doing:\n- Wheat in North Plot: stage VEGETATIVE, health HEALTHY", provider_name: "mock-copilot", is_mock: true, referenced_entities: [{ entity_type: "crop", entity_id: "c1", label: "Wheat" }], context_freshness_warnings: [], created_at: "2026-08-12T09:00:05Z" },
          ],
        });
      }
      return Promise.resolve([]);
    });

    render(<CopilotPage />);
    const convButton = await screen.findByRole("button", { name: /how are my crops doing/i });
    await userEvent.click(convButton);

    expect(await screen.findByText(/wheat in north plot/i)).toBeInTheDocument();
    expect(screen.getByText("Wheat")).toBeInTheDocument(); // rendered reference chip
    expect(screen.getByText(/mock model/i)).toBeInTheDocument();
  });

  it("starts a new conversation and sends a message that gets a grounded assistant reply", async () => {
    mockedApi.get.mockResolvedValue([]);
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/copilot/conversations") {
        return Promise.resolve({ id: "conv-new", title: null, created_at: "2026-08-12T10:00:00Z", updated_at: "2026-08-12T10:00:00Z" });
      }
      if (path === "/copilot/conversations/conv-new/messages") {
        return Promise.resolve({
          id: "m2", role: "ASSISTANT", content: "You have 1 farm(s) with 1 field(s) and 1 crop(s) tracked.",
          provider_name: "mock-copilot", is_mock: true,
          referenced_entities: [{ entity_type: "farm", entity_id: "f1", label: "Green Valley Farm" }],
          context_freshness_warnings: [], created_at: "2026-08-12T10:00:05Z",
        });
      }
      return Promise.resolve({});
    });

    render(<CopilotPage />);
    await screen.findByText(/ask agrimind copilot about your farm/i);

    const input = screen.getByLabelText(/ask agrimind copilot/i);
    await userEvent.type(input, "Summarize my farm");
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() =>
      expect(mockedApi.post).toHaveBeenCalledWith("/copilot/conversations/conv-new/messages", { content: "Summarize my farm" })
    );
    expect(await screen.findByText(/you have 1 farm\(s\)/i)).toBeInTheDocument();
    expect(screen.getByText("Green Valley Farm")).toBeInTheDocument();
  });

  it("sends a suggested question directly", async () => {
    mockedApi.get.mockResolvedValue([]);
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/copilot/conversations") {
        return Promise.resolve({ id: "conv-sq", title: null, created_at: "2026-08-12T10:00:00Z", updated_at: "2026-08-12T10:00:00Z" });
      }
      return Promise.resolve({
        id: "m2", role: "ASSISTANT", content: "No active risks and no high-priority recommendations right now.",
        provider_name: "mock-copilot", is_mock: true, referenced_entities: [], context_freshness_warnings: [],
        created_at: "2026-08-12T10:00:05Z",
      });
    });

    render(<CopilotPage />);
    await userEvent.click(await screen.findByRole("button", { name: /what needs my attention today/i }));

    expect(await screen.findByText(/no active risks and no high-priority recommendations/i)).toBeInTheDocument();
  });

  it("shows an error state and allows retry when sending a message fails", async () => {
    mockedApi.get.mockResolvedValue([]);
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/copilot/conversations") {
        return Promise.resolve({ id: "conv-err", title: null, created_at: "2026-08-12T10:00:00Z", updated_at: "2026-08-12T10:00:00Z" });
      }
      return Promise.reject(new ApiError(503, "http_error", "Copilot is unavailable right now."));
    });

    render(<CopilotPage />);
    const input = screen.getByLabelText(/ask agrimind copilot/i);
    await userEvent.type(input, "Hello");
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Copilot is unavailable right now.");
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("does not render fabricated referenced entities beyond what the API returned", async () => {
    mockedApi.get.mockResolvedValue([]);
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/copilot/conversations") {
        return Promise.resolve({ id: "conv-clean", title: null, created_at: "2026-08-12T10:00:00Z", updated_at: "2026-08-12T10:00:00Z" });
      }
      return Promise.resolve({
        id: "m2", role: "ASSISTANT", content: "You haven't added any farms yet.",
        provider_name: "mock-copilot", is_mock: true, referenced_entities: [], context_freshness_warnings: [],
        created_at: "2026-08-12T10:00:05Z",
      });
    });

    render(<CopilotPage />);
    const input = screen.getByLabelText(/ask agrimind copilot/i);
    await userEvent.type(input, "Summarize my farm");
    await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

    await screen.findByText(/haven't added any farms yet/i);
    expect(screen.queryByText("Green Valley Farm")).not.toBeInTheDocument();
  });
});
