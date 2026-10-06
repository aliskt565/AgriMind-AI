import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FarmsPage from "../page";
import { api, ApiError } from "@/lib/api";

jest.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return { ...actual, api: { get: jest.fn(), post: jest.fn() } };
});

const mockedApi = api as jest.Mocked<typeof api>;

describe("FarmsPage", () => {
  beforeEach(() => {
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
  });

  it("shows an error state with retry when farms fail to load", async () => {
    mockedApi.get.mockRejectedValue(new ApiError(500, "internal_error", "Could not load your farms."));
    render(<FarmsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your farms.");
  });

  it("shows the empty state when the farmer has no farms", async () => {
    mockedApi.get.mockResolvedValue([]);
    render(<FarmsPage />);
    expect(await screen.findByText(/no farms yet/i)).toBeInTheDocument();
  });

  it("renders real farm data returned by the API, not placeholder content", async () => {
    mockedApi.get.mockResolvedValue([
      { id: "farm-1", name: "Green Valley Farm", total_area_acres: 12.5, location: "Sheikhupura Road", latitude: null, longitude: null, status: "ACTIVE", field_count: 2 },
    ]);
    render(<FarmsPage />);
    expect(await screen.findByText("Green Valley Farm")).toBeInTheDocument();
    expect(screen.getByText(/sheikhupura road/i)).toBeInTheDocument();
    expect(screen.getByText(/2 fields/i)).toBeInTheDocument();
  });

  it("creates a farm and refreshes the list", async () => {
    mockedApi.get
      .mockResolvedValueOnce([]) // initial load
      .mockResolvedValueOnce([
        { id: "farm-1", name: "New Farm", total_area_acres: null, location: null, latitude: null, longitude: null, status: "ACTIVE", field_count: 0 },
      ]); // after create, reload
    mockedApi.post.mockResolvedValue({ id: "farm-1" });

    render(<FarmsPage />);
    await screen.findByText(/no farms yet/i);

    const addButtons = screen.getAllByRole("button", { name: /add farm/i });
    await userEvent.click(addButtons[0]);
    await userEvent.type(screen.getByLabelText(/farm name/i), "New Farm");
    await userEvent.click(screen.getByRole("button", { name: /create farm/i }));

    await waitFor(() =>
      expect(mockedApi.post).toHaveBeenCalledWith("/farms", expect.objectContaining({ name: "New Farm" }))
    );
    expect(await screen.findByText("New Farm")).toBeInTheDocument();
  });

  it("shows a form error message when farm creation fails", async () => {
    mockedApi.get.mockResolvedValue([]);
    mockedApi.post.mockRejectedValue(new ApiError(422, "validation_error", "Farm name is required."));

    render(<FarmsPage />);
    await screen.findByText(/no farms yet/i);
    const addButtons = screen.getAllByRole("button", { name: /add farm/i });
    await userEvent.click(addButtons[0]);
    await userEvent.type(screen.getByLabelText(/farm name/i), "X");
    await userEvent.click(screen.getByRole("button", { name: /create farm/i }));

    expect(await screen.findByText("Farm name is required.")).toBeInTheDocument();
  });
});
