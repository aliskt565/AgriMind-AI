import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "@/app/(auth)/register/page";
import { ApiError } from "@/lib/api";

const mockRegister = jest.fn();
const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ register: mockRegister }),
}));

describe("RegisterPage", () => {
  beforeEach(() => {
    mockRegister.mockReset();
    mockPush.mockReset();
  });

  it("submits registration details and redirects to the dashboard on success", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    render(<RegisterPage />);

    await userEvent.type(screen.getByLabelText(/full name/i), "Bilal Ahmed");
    await userEvent.type(screen.getByLabelText(/email/i), "bilal@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "SecurePass1");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() =>
      expect(mockRegister).toHaveBeenCalledWith({
        email: "bilal@example.com",
        password: "SecurePass1",
        full_name: "Bilal Ahmed",
        location: undefined,
      })
    );
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows the server error when the email is already registered", async () => {
    mockRegister.mockRejectedValueOnce(new ApiError(409, "http_error", "An account with this email already exists"));
    render(<RegisterPage />);

    await userEvent.type(screen.getByLabelText(/full name/i), "Bilal Ahmed");
    await userEvent.type(screen.getByLabelText(/email/i), "bilal@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "SecurePass1");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("An account with this email already exists");
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("enforces an 8-character minimum password client-side", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("minLength", "8");
  });
});
