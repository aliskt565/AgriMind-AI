import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardPage from "../page";
import { api, ApiError } from "@/lib/api";

jest.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockUser = { id: "u1", email: "farmer@example.com", role: "FARMER", is_active: true, is_email_verified: true };

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockUser }),
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return { ...actual, api: { get: jest.fn(), post: jest.fn() } };
});

const mockedApi = api as jest.Mocked<typeof api>;

describe("DashboardPage", () => {
  beforeEach(() => {
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
  });

  it("shows an error state and allows retry when the summary request fails", async () => {
    mockedApi.get.mockRejectedValue(new ApiError(500, "internal_error", "Could not load your dashboard."));
    render(<DashboardPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your dashboard.");
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows the empty-farms prompt when the farmer has no farms yet", async () => {
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === "/dashboard/summary") {
        return { farm_count: 0, field_count: 0, active_crop_count: 0, active_risk_count: 0, active_recommendation_count: 0 };
      }
      return [];
    });
    render(<DashboardPage />);

    expect(await screen.findByText(/no farms yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /go to farms/i })).toHaveAttribute("href", "/farms");
  });

  it("renders KPI values and the risks/recommendations panels for an active farmer", async () => {
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === "/dashboard/summary") {
        return { farm_count: 2, field_count: 3, active_crop_count: 5, active_risk_count: 1, active_recommendation_count: 1 };
      }
      if (path === "/risk") {
        return [
          {
            id: "risk-1", farm_id: "f1", field_id: "fl1", crop_id: null,
            risk_type: "DATA_QUALITY", risk_level: "MODERATE", confidence: "HIGH",
            reason: "Soil type is not set for this field.", recommended_action: "Update soil info.", status: "ACTIVE",
          },
        ];
      }
      if (path === "/recommendations") {
        return [
          {
            id: "rec-1", farm_id: "f1", field_id: "fl1", crop_id: "c1",
            category: "HARVEST_TIMING", priority: "MEDIUM", status: "ACTIVE",
            text: "This crop has reached maturity -- plan your harvest window soon.",
            trigger_reason: "Triggered by crop stage: MATURITY",
          },
        ];
      }
      return [];
    });
    render(<DashboardPage />);

    expect(await screen.findByText("2")).toBeInTheDocument(); // farm_count KPI
    expect(screen.getByText("Soil type is not set for this field.")).toBeInTheDocument();
    expect(screen.getByText(/plan your harvest window soon/i)).toBeInTheDocument();
  });

  it("dismisses a recommendation and removes it from the list", async () => {
    mockedApi.get.mockImplementation(async (path: string) => {
      if (path === "/dashboard/summary") {
        return { farm_count: 1, field_count: 1, active_crop_count: 1, active_risk_count: 0, active_recommendation_count: 1 };
      }
      if (path === "/recommendations") {
        return [
          {
            id: "rec-1", farm_id: "f1", field_id: "fl1", crop_id: "c1",
            category: "HARVEST_TIMING", priority: "MEDIUM", status: "ACTIVE",
            text: "Plan your harvest window soon.", trigger_reason: "Triggered by crop stage: MATURITY",
          },
        ];
      }
      return [];
    });
    mockedApi.post.mockResolvedValue(undefined);

    render(<DashboardPage />);
    expect(await screen.findByText(/plan your harvest window soon/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/recommendations/rec-1/dismiss"));
    await waitFor(() => expect(screen.queryByText(/plan your harvest window soon/i)).not.toBeInTheDocument());
  });
});
