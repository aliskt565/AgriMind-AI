import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/(auth)/login/page";
import { ApiError } from "@/lib/api";

const mockLogin = jest.fn();
const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ login: mockLogin }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockPush.mockReset();
  });

  it("submits credentials and redirects to the dashboard on success", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText(/email/i), "farmer@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "SecurePass1");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));

    await waitFor(() => expect(mockLogin).toHaveBeenCalledWith("farmer@example.com", "SecurePass1"));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows the server error message when login fails", async () => {
    mockLogin.mockRejectedValueOnce(new ApiError(401, "auth_error", "Incorrect email or password"));
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText(/email/i), "farmer@example.com");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password");
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("requires email and password before submission", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeRequired();
    expect(screen.getByLabelText(/password/i)).toBeRequired();
  });
});
