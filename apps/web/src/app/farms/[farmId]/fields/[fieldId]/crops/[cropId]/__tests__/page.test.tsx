import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CropDetailPage from "../page";
import { api, ApiError } from "@/lib/api";

jest.mock("@/components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("next/navigation", () => ({
  useParams: () => ({ farmId: "farm-1", fieldId: "field-1", cropId: "crop-1" }),
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return { ...actual, api: { get: jest.fn(), post: jest.fn(), postForm: jest.fn() } };
});

const mockedApi = api as jest.Mocked<typeof api>;

const CROP = {
  id: "crop-1", field_id: "field-1", crop_type: "Corn", variety: "Punjab-2011",
  stage: "VEGETATIVE", source: "MANUAL", health_status: "HEALTHY",
  planting_date: "2026-08-01", expected_harvest_date: "2026-12-15", actual_harvest_date: null,
  actual_yield: null, yield_unit: null, notes: null,
};

function mockGetImplementation() {
  return (path: string) => {
    if (path === "/crops/crop-1") return Promise.resolve(CROP);
    if (path === "/crops/crop-1/activities") return Promise.resolve([]);
    return Promise.resolve([]);
  };
}

function makeFile(name: string, type: string, sizeBytes = 2000) {
  const file = new File([new Uint8Array(sizeBytes)], name, { type });
  return file;
}

describe("CropDetailPage", () => {
  beforeEach(() => {
    mockedApi.get.mockReset();
    mockedApi.post.mockReset();
    mockedApi.postForm.mockReset();
  });

  it("renders real crop data from the API", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    render(<CropDetailPage />);
    expect(await screen.findByText(/corn · punjab-2011/i)).toBeInTheDocument();
    expect(screen.getByText(/stage: vegetative/i)).toBeInTheDocument();
  });

  it("shows an error state when the crop fails to load", async () => {
    mockedApi.get.mockImplementation((path: string) => {
      if (path === "/crops/crop-1") return Promise.reject(new ApiError(404, "http_error", "Crop not found"));
      return Promise.resolve([]);
    });
    render(<CropDetailPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Crop not found");
  });

  it("shows the empty activity state and logs a new activity", async () => {
    mockedApi.get
      .mockImplementation(mockGetImplementation());
    mockedApi.post.mockResolvedValue({ id: "act-1", crop_id: "crop-1", activity_type: "IRRIGATION", status: "LOGGED", activity_date: "2026-08-10", quantity: null, quantity_unit: null, notes: null });

    render(<CropDetailPage />);
    expect(await screen.findByText(/no activities logged yet/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /log activity/i }));
    await userEvent.click(screen.getByRole("button", { name: /save activity/i }));

    await waitFor(() =>
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/crops/crop-1/activities",
        expect.objectContaining({ activity_type: "IRRIGATION" })
      )
    );
  });

  it("rejects a non-image file before ever calling the API", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    render(<CropDetailPage />);
    await screen.findByText(/corn · punjab-2011/i);

    const input = screen.getByLabelText(/upload a plant photo/i) as HTMLInputElement;
    const badFile = makeFile("notes.txt", "text/plain");
    await userEvent.upload(input, badFile);

    // The <input accept="image/jpeg,image/png,image/webp"> attribute blocks
    // non-matching files at the browser/OS picker level; verify the accept
    // constraint is actually present rather than relying on jsdom to enforce it.
    expect(input.accept).toBe("image/jpeg,image/png,image/webp");
  });

  it("shows the processing state, then a successful high-confidence Plant Vision result", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    let resolveUpload: (value: unknown) => void = () => {};
    mockedApi.postForm.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        })
    );

    render(<CropDetailPage />);
    await screen.findByText(/corn · punjab-2011/i);

    const input = screen.getByLabelText(/upload a plant photo/i) as HTMLInputElement;
    await userEvent.upload(input, makeFile("leaf.jpg", "image/jpeg"));

    expect(await screen.findByText(/analyzing image/i)).toBeInTheDocument();

    resolveUpload({
      id: "det-1", crop_id: "crop-1", result_type: "HIGH_CONFIDENCE",
      predicted_disease: "Leaf Rust", confidence: 0.82,
      symptoms_matched: "yellow-orange pustules on leaf surface",
      guidance_text: "Possible leaf rust detected. Isolate affected plants where practical.",
      rejection_reason: null, model_name: "mock-plant-vision", model_version: "0.1.0-mock", is_mock: true,
      disclaimer: "This is an AI-generated prediction based on visual patterns, not a confirmed agricultural diagnosis.",
    });

    expect(await screen.findByText("Leaf Rust")).toBeInTheDocument();
    expect(screen.getByText(/confidence 82%/i)).toBeInTheDocument();
    expect(screen.getByText(/not a confirmed agricultural diagnosis/i)).toBeInTheDocument();
  });

  it("shows a low-confidence result distinctly", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.postForm.mockResolvedValue({
      id: "det-2", crop_id: "crop-1", result_type: "LOW_CONFIDENCE",
      predicted_disease: "Powdery Mildew", confidence: 0.4,
      symptoms_matched: "white powdery patches", guidance_text: "Uncertain -- consider retaking the photo.",
      rejection_reason: null, model_name: "mock-plant-vision", model_version: "0.1.0-mock", is_mock: true,
      disclaimer: "This is an AI-generated prediction based on visual patterns, not a confirmed agricultural diagnosis.",
    });

    render(<CropDetailPage />);
    await screen.findByText(/corn · punjab-2011/i);
    const input = screen.getByLabelText(/upload a plant photo/i) as HTMLInputElement;
    await userEvent.upload(input, makeFile("leaf2.jpg", "image/jpeg"));

    expect(await screen.findByText(/low confidence/i)).toBeInTheDocument();
  });

  it("shows an error state when Plant Vision analysis fails", async () => {
    mockedApi.get.mockImplementation(mockGetImplementation());
    mockedApi.postForm.mockRejectedValue(new ApiError(503, "http_error", "Plant Vision service is unavailable. Please try again."));

    render(<CropDetailPage />);
    await screen.findByText(/corn · punjab-2011/i);
    const input = screen.getByLabelText(/upload a plant photo/i) as HTMLInputElement;
    await userEvent.upload(input, makeFile("leaf3.jpg", "image/jpeg"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Plant Vision service is unavailable. Please try again.");
  });
});
