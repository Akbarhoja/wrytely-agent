import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { WhatsAppConnection } from "../components/whatsapp-connection";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const disconnected = {
  linked: false,
  phoneLast4: null,
  destination: "15555550100",
  configured: true,
  preferences: null,
  delivery: null,
};
function actions() {
  return {
    onLink: vi.fn(),
    onRefresh: vi.fn(),
    onExpire: vi.fn(),
    onDisconnect: vi.fn(async () => true),
    onSave: vi.fn(async () => true),
  };
}

describe("WhatsApp connection controls", () => {
  it("does not offer private actions while signed out or unconfigured", () => {
    render(<WhatsAppConnection mode="unconfigured" {...actions()} />);
    expect(screen.getByText(/WhatsApp setup is not available yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Create verification/ })).toBeNull();
  });
  it("keeps unknown status distinct from disconnected", () => {
    const callbacks = actions();
    render(<WhatsAppConnection mode="error" {...callbacks} />);
    expect(screen.getByText(/couldn’t check your connection/)).toBeTruthy();
    expect(screen.queryByText("Not connected")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Check connection" }));
    expect(callbacks.onRefresh).toHaveBeenCalledTimes(1);
  });
  it("shows a masked memory-only code and clears its display at expiry", async () => {
    vi.useFakeTimers();
    const callbacks = actions();
    render(
      <WhatsAppConnection
        mode="ready"
        connection={disconnected}
        challenge={{ message: "LINK secret-test-value", expiresAt: Date.now() + 2000 }}
        {...callbacks}
      />,
    );
    const code = screen.getByLabelText("Verification message") as HTMLInputElement;
    expect(code.type).toBe("password");
    expect(code.value).toBe("LINK secret-test-value");
    fireEvent.click(screen.getByRole("button", { name: "Show verification message" }));
    expect(code.type).toBe("text");
    expect(document.querySelector('a[href*="secret-test-value"]')).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(2100));
    expect(screen.queryByLabelText("Verification message")).toBeNull();
    expect(callbacks.onExpire).toHaveBeenCalledTimes(1);
  });
  it("requires a separate confirmation before disconnecting", async () => {
    const callbacks = actions();
    render(
      <WhatsAppConnection
        mode="ready"
        connection={{ ...disconnected, linked: true, phoneLast4: "0123" }}
        {...callbacks}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Disconnect WhatsApp" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep connection" }));
    expect(callbacks.onDisconnect).not.toHaveBeenCalled();
    expect(screen.getByText(/Queued replies will be cancelled/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Keep connection" }));
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Disconnect WhatsApp" }),
    );
    expect(callbacks.onDisconnect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect WhatsApp" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm disconnect" }));
    await waitFor(() => expect(callbacks.onDisconnect).toHaveBeenCalledTimes(1));
  });

  it("reconciles saved preferences while retaining an explicitly edited draft", async () => {
    const callbacks = actions();
    const initial = {
      ...disconnected,
      preferences: { consent: false, timezone: "UTC", quiet_start: 22, quiet_end: 7 },
    };
    const { rerender } = render(
      <WhatsAppConnection mode="ready" connection={initial} {...callbacks} />,
    );
    const updated = {
      ...initial,
      preferences: { ...initial.preferences, consent: true, timezone: "America/Denver" },
    };
    rerender(<WhatsAppConnection mode="ready" connection={updated} {...callbacks} />);
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).value).toBe(
      "America/Denver",
    );
    expect(
      (screen.getByLabelText("Allow Wrytely to send me WhatsApp replies") as HTMLInputElement)
        .checked,
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Your timezone"), {
      target: { value: "Europe/London" },
    });
    const latest = {
      ...updated,
      preferences: { ...updated.preferences, timezone: "America/Chicago" },
    };
    rerender(<WhatsAppConnection mode="ready" connection={latest} {...callbacks} />);
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).value).toBe(
      "Europe/London",
    );
    expect(screen.getByText(/Saved preferences changed/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Use saved preferences" }));
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).value).toBe(
      "America/Chicago",
    );
  });

  it("prevents duplicate link requests while one is pending", async () => {
    let finish!: () => void;
    const callbacks = {
      ...actions(),
      onLink: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            finish = resolve;
          }),
      ),
    };
    render(<WhatsAppConnection mode="ready" connection={disconnected} {...callbacks} />);
    const button = screen.getByRole("button", { name: "Create verification message" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(callbacks.onLink).toHaveBeenCalledTimes(1);
    await act(async () => finish());
  });
  it("validates and explicitly saves preferences without inventing saved consent", async () => {
    const callbacks = actions();
    render(<WhatsAppConnection mode="ready" connection={disconnected} {...callbacks} />);
    expect(screen.getByText("Preferences have not been saved yet.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Your timezone"), {
      target: { value: "Invalid/Timezone" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    expect(screen.getByText("Choose a valid timezone, such as America/Denver.")).toBeTruthy();
    expect(callbacks.onSave).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Your timezone"), {
      target: { value: "America/Denver" },
    });
    fireEvent.click(screen.getByLabelText("Allow Wrytely to send me WhatsApp replies"));
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    await waitFor(() =>
      expect(callbacks.onSave).toHaveBeenCalledWith({
        consent: true,
        timezone: "America/Denver",
        quiet_start: 22,
        quiet_end: 7,
      }),
    );
  });
});
