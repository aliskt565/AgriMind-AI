import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "../AppShell";

const mockPush = jest.fn();
const mockLogout = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
}));

let mockAuthState: { user: unknown; isLoading: boolean } = { user: null, isLoading: true };

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ ...mockAuthState, logout: mockLogout }),
}));

describe("AppShell", () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockLogout.mockReset();
  });

  it("shows a loading indicator while auth state is resolving", () => {
    mockAuthState = { user: null, isLoading: true };
    render(<AppShell><div>Protected content</div></AppShell>);
    expect(screen.getByText(/loading agrimind ai/i)).toBeInTheDocument();
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("redirects to /login when there is no authenticated user", async () => {
    mockAuthState = { user: null, isLoading: false };
    render(<AppShell><div>Protected content</div></AppShell>);
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
  });

  it("renders protected content once authenticated", () => {
    mockAuthState = { user: { id: "u1", email: "farmer@example.com", role: "FARMER", is_active: true, is_email_verified: true }, isLoading: false };
    render(<AppShell><div>Protected content</div></AppShell>);
    expect(screen.getByText("Protected content")).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("calls logout when the Log out button is clicked", async () => {
    mockAuthState = { user: { id: "u1", email: "farmer@example.com", role: "FARMER", is_active: true, is_email_verified: true }, isLoading: false };
    render(<AppShell><div>Protected content</div></AppShell>);

    const logoutButtons = screen.getAllByRole("button", { name: /log out/i });
    await userEvent.click(logoutButtons[0]);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});
