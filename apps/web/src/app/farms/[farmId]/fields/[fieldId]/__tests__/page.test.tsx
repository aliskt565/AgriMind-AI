import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FieldDetailPage from "../page";
import { api, ApiError } from "@/lib/api";

jest.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("next/navigation", () => ({
  useParams: () => ({ farmId: "farm-1", fieldId: "field-1" }),
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return { ...actual, api: { get: jest.fn(), post: jest.fn() } };
});

const mockedApi = api as jest.Mocked<typeof api>;

const FIELD = {
  id: "field-1", farm_id: "farm-1", name: "North Plot", area_acres: 4,
  soil_type: "LOAMY", irrigation_type: "DRIP", status: "ACTIVE", crop_count: 0,
};

const WEATHER = {
  field_id: "field-1", source: "mock-weather", fetched_at: "2026-08-12T10:00:00Z", is_stale: false,
  temperature_celsius: 31.4, humidity_percent: 55, rainfall_mm_last_24h: 2.1,
  forecast_summary: "Clear skies expected for the next 3 days.", extreme_weather_alert: null,
};

function mockGetImplementation() {
  return (path: string) => {
    if (path === "/fields/field-1") return Promise.resolve(FIELD);
    if (path === "/fields/field-1/crops") return Promise.resolve([]);
    if (path === "/weather/fields/field-1") return Promise.resolve(WEATHER);
    return Promise.resolve([]);
  };
}

describe("FieldDetailPage", () => {
  beforeEach(() => {
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
  });

  it("renders real field data and the weather widget from the API", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    render(<FieldDetailPage />);

    expect(await screen.findByText("North Plot")).toBeInTheDocument();
    expect(await screen.findByText("31.4°C")).toBeInTheDocument();
    expect(screen.getByText(/clear skies expected/i)).toBeInTheDocument();
    expect(screen.getByText(/mock-weather/i)).toBeInTheDocument();
  });

  it("shows a stale indicator when the weather snapshot is marked stale", async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/weather/fields/field-1") return Promise.resolve({ ...WEATHER, is_stale: true });
      return mockGetImplementation()(path);
    });
    render(<FieldDetailPage />);
    expect(await screen.findByText(/stale/i)).toBeInTheDocument();
  });

  it("shows an extreme weather alert distinctly when present", async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/weather/fields/field-1") {
        return Promise.resolve({ ...WEATHER, extreme_weather_alert: "Heavy rainfall warning issued for this region." });
      }
      return mockGetImplementation()(path);
    });
    render(<FieldDetailPage />);
    expect(await screen.findByText(/heavy rainfall warning/i)).toBeInTheDocument();
  });

  it("shows an error state when the field fails to load", async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/fields/field-1") return Promise.reject(new ApiError(404, "http_error", "Field not found"));
      return Promise.resolve([]);
    });
    render(<FieldDetailPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Field not found");
  });

  it("shows the empty crops state when the field has no crops yet", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    render(<FieldDetailPage />);
    expect(await screen.findByText(/no crops yet/i)).toBeInTheDocument();
  });

  it("runs a risk scan and shows a summary message", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/risk/fields/field-1/scan") {
        return Promise.resolve([{ risk_type: "DATA_QUALITY" }]);
      }
      return Promise.resolve({});
    });

    render(<FieldDetailPage />);
    await screen.findByText("North Plot");

    await userEvent.click(screen.getByRole("button", { name: /run risk scan/i }));

    await waitFor(() => expect(mockedApi.post).toHaveBeenCalledWith("/risk/fields/field-1/scan"));
    expect(await screen.findByText(/1 active risk found/i)).toBeInTheDocument();
  });

  it("shows a no-risk message when the scan finds nothing", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/risk/fields/field-1/scan") return Promise.resolve([]);
      return Promise.resolve({});
    });

    render(<FieldDetailPage />);
    await screen.findByText("North Plot");
    await userEvent.click(screen.getByRole("button", { name: /run risk scan/i }));

    expect(await screen.findByText(/no risks detected/i)).toBeInTheDocument();
  });

  it("requests AI Crop Advisor suggestions and displays ranked candidates with separate suitability/confidence/risk", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/ai/crop-intelligence/fields/field-1") {
        return Promise.resolve({
          id: "pred-1", field_id: "field-1", is_mock: true, model_name: "mock-crop-intelligence", model_version: "0.1.0-mock",
          important_assumptions: ["Assumes normal rainfall for the season."],
          candidates: [
            { crop_type: "Wheat", suitability_score: 82, confidence: "HIGH", explanation: "Key factors considered: loamy soil favors wheat.", limiting_factors: [], risk_note: null },
          ],
        });
      }
      return Promise.resolve({});
    });

    render(<FieldDetailPage />);
    await screen.findByText("North Plot");
    await userEvent.click(screen.getByRole("button", { name: /ask ai crop advisor/i }));

    expect(await screen.findByText("Wheat")).toBeInTheDocument();
    expect(screen.getByText(/suitability 82\/100/i)).toBeInTheDocument();
    expect(screen.getByText(/confidence high/i)).toBeInTheDocument();
    expect(screen.getByText(/ai generated · mock model/i)).toBeInTheDocument();
  });

  it("shows an error state when the AI Crop Advisor request fails", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/ai/crop-intelligence/fields/field-1") {
        return Promise.reject(new ApiError(503, "http_error", "Crop Intelligence service is unavailable. Please try again."));
      }
      return Promise.resolve({});
    });

    render(<FieldDetailPage />);
    await screen.findByText("North Plot");
    await userEvent.click(screen.getByRole("button", { name: /ask ai crop advisor/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Crop Intelligence service is unavailable. Please try again.");
  });

  it("creates a crop with a planting date so the risk engine has a real reference point", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.post.mockImplementation((path: string) => {
      if (path === "/fields/field-1/crops") {
        return Promise.resolve({
          id: "crop-1", field_id: "field-1", crop_type: "Wheat", variety: null, stage: "PLANNED",
          source: "MANUAL", health_status: "HEALTHY", planting_date: "2026-08-15", expected_harvest_date: null,
          actual_harvest_date: null, actual_yield: null, yield_unit: null, notes: null,
        });
      }
      return Promise.resolve({});
    });

    render(<FieldDetailPage />);
    await screen.findByText("North Plot");
    const addCropButtons = screen.getAllByRole("button", { name: /add crop/i });
    await userEvent.click(addCropButtons[0]);
    await userEvent.type(screen.getByLabelText(/crop type/i), "Wheat");
    await userEvent.click(screen.getByRole("button", { name: /create crop/i }));

    await waitFor(() =>
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/fields/field-1/crops",
        expect.objectContaining({ crop_type: "Wheat", planting_date: expect.any(String) })
      )
    );
    const [, body] = mockedApi.post.mock.calls.find(([path]) => path === "/fields/field-1/crops")!;
    expect((body as { planting_date: string }).planting_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
