import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { storage } from "../../utils/storage";

const mocks = vi.hoisted(() => ({
  verifyToken: vi.fn(),
  setLocation: vi.fn()
}));

vi.mock("wouter", () => ({
  useLocation: () => ["/login", mocks.setLocation]
}));

vi.mock("../../utils/api-client", () => ({
  verifyToken: mocks.verifyToken
}));

import Login from "../../views/login";

function submit() {
  fireEvent.submit(
    screen.getByPlaceholderText("Authorization Key").closest("form")!
  );
}

describe("Login", () => {
  beforeEach(() => {
    localStorage.clear();
    mocks.verifyToken.mockReset();
    mocks.setLocation.mockReset();
  });

  it("sets the page title", () => {
    render(<Login />);

    expect(document.title).toBe("Login");
  });

  it("prefills the stored token", () => {
    storage.set("auth-token", "stored-token");

    render(<Login />);

    expect(screen.getByPlaceholderText("Authorization Key")).toHaveValue(
      "stored-token"
    );
  });

  it("rejects an empty submission without calling the API", () => {
    render(<Login />);

    fireEvent.change(screen.getByPlaceholderText("Authorization Key"), {
      target: { value: "   " }
    });
    submit();

    expect(
      screen.getByText("Please enter your Authorization Key")
    ).toBeInTheDocument();
    expect(mocks.verifyToken).not.toHaveBeenCalled();
  });

  it("shows an error for an invalid token", async () => {
    mocks.verifyToken.mockResolvedValue(false);

    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Authorization Key"), {
      target: { value: "wrong" }
    });
    submit();

    await waitFor(() =>
      expect(screen.getByText("Invalid Authorization Key")).toBeInTheDocument()
    );
    expect(mocks.verifyToken).toHaveBeenCalledWith("wrong");
    expect(storage.get("auth-token")).toBeNull();
    expect(mocks.setLocation).not.toHaveBeenCalled();
  });

  it("stores a valid token and navigates to the dashboard", async () => {
    mocks.verifyToken.mockResolvedValue(true);

    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Authorization Key"), {
      target: { value: "  secret  " }
    });
    submit();

    await waitFor(() =>
      expect(mocks.setLocation).toHaveBeenCalledWith("/dashboard")
    );
    expect(storage.get("auth-token")).toBe("secret");
  });

  it("shows a verification error when the request throws", async () => {
    mocks.verifyToken.mockRejectedValue(new Error("boom"));

    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Authorization Key"), {
      target: { value: "secret" }
    });
    submit();

    await waitFor(() =>
      expect(screen.getByText("Verification failed")).toBeInTheDocument()
    );
  });

  it("disables the submit button while verifying", () => {
    mocks.verifyToken.mockReturnValue(new Promise(() => {}));

    render(<Login />);
    fireEvent.change(screen.getByPlaceholderText("Authorization Key"), {
      target: { value: "secret" }
    });
    submit();

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
