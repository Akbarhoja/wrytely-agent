import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { WhatsAppConnection } from "../components/whatsapp-connection";
import { useWhatsAppConnection } from "../lib/use-whatsapp-connection";

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
const status = {
  linked: false,
  phone_last4: null,
  destination: "15555550100",
  configured: true,
  preferences: null,
  latest_delivery: null,
};

describe("private connection controller", () => {
  it.each([403, 404])("offers recovery after a mutation is rejected with %s", async (code) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, options?: RequestInit) =>
        options?.method === "POST"
          ? Response.json({ detail: "Access unavailable" }, { status: code })
          : Response.json(status),
      ),
    );
    const { result } = renderHook(() => useWhatsAppConnection("alice"));
    await waitFor(() => expect(result.current.mode).toBe("ready"));
    await act(async () => {
      await result.current.onLink();
    });
    expect(result.current.mode).toBe("error");
    expect(result.current.connection).toBeUndefined();
    await act(async () => {
      await result.current.onRefresh();
    });
    expect(result.current.mode).toBe("ready");
  });
  it("keeps unsaved preferences through a failed refresh and recovery", async () => {
    const fetcher = vi.fn(async () => Response.json(status));
    vi.stubGlobal("fetch", fetcher);
    function Panel() {
      const data = useWhatsAppConnection("alice");
      return <WhatsAppConnection {...data} />;
    }
    render(<Panel />);
    await waitFor(() => expect(screen.getByLabelText("Your timezone")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Your timezone"), {
      target: { value: "Europe/London" },
    });
    fetcher.mockImplementationOnce(async () =>
      Response.json({ detail: "Unavailable" }, { status: 503 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh connection" }));
    await waitFor(() => expect(screen.getByText(/couldn’t check your connection/)).toBeTruthy());
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).value).toBe(
      "Europe/London",
    );
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Check connection" }));
    await waitFor(() =>
      expect((screen.getByLabelText("Your timezone") as HTMLInputElement).disabled).toBe(false),
    );
    expect((screen.getByLabelText("Your timezone") as HTMLInputElement).value).toBe(
      "Europe/London",
    );
  });
  it("loads only after provisioning and keeps account switches private", async () => {
    const fetcher = vi.fn(async () => Response.json(status));
    vi.stubGlobal("fetch", fetcher);
    const { result, rerender } = renderHook(
      ({ user }: { user?: string }) => useWhatsAppConnection(user),
      {
        initialProps: { user: undefined as string | undefined },
      },
    );
    expect(fetcher).not.toHaveBeenCalled();
    rerender({ user: "alice" });
    await waitFor(() => expect(result.current.connection?.destination).toBe(status.destination));
    fetcher.mockImplementation(() => new Promise(() => {}));
    rerender({ user: "bob" });
    expect(result.current.connection).toBeUndefined();
    expect(result.current.challenge).toBeUndefined();
  });
  it("never replays an uncertain mutation and requires a fresh status read", async () => {
    const fetcher = vi.fn(async (_url: unknown, options?: RequestInit) => {
      if (options?.method === "POST") throw new TypeError("Connection lost");
      return Response.json(status);
    });
    vi.stubGlobal("fetch", fetcher);
    const { result } = renderHook(() => useWhatsAppConnection("alice"));
    await waitFor(() => expect(result.current.mode).toBe("ready"));
    await act(async () => {
      await result.current.onLink();
    });
    expect(result.current.uncertain).toBe(true);
    await act(async () => {
      await result.current.onLink();
    });
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
    await act(async () => {
      await result.current.onRefresh();
    });
    expect(result.current.uncertain).toBe(false);
  });
  it("retains codes only in memory, expires them, and clears private state on 401", async () => {
    const fetcher = vi.fn(async (_url: unknown, options?: RequestInit) =>
      Response.json(
        options?.method === "POST"
          ? { message: "LINK private-code", expires_at: new Date(Date.now() + 60000).toISOString() }
          : status,
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    const { result } = renderHook(() => useWhatsAppConnection("alice"));
    await waitFor(() => expect(result.current.mode).toBe("ready"));
    await act(async () => {
      await result.current.onLink();
    });
    expect(result.current.challenge?.message).toBe("LINK private-code");
    act(() => result.current.onExpire());
    expect(result.current.challenge).toBeUndefined();
    fetcher.mockImplementation(async () => Response.json({ detail: "Expired" }, { status: 401 }));
    await act(async () => {
      await result.current.onRefresh();
    });
    expect(result.current.mode).toBe("expired");
    expect(result.current.connection).toBeUndefined();
  });
  it("does not report saved preferences if the confirming read fails", async () => {
    let changed = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, options?: RequestInit) => {
        if (options?.method === "POST") {
          changed = true;
          return Response.json({ saved: true });
        }
        if (changed) return Response.json({ detail: "Storage unavailable" }, { status: 503 });
        return Response.json(status);
      }),
    );
    const { result } = renderHook(() => useWhatsAppConnection("alice"));
    await waitFor(() => expect(result.current.mode).toBe("ready"));
    let saved;
    await act(async () => {
      saved = await result.current.onSave({
        consent: true,
        timezone: "UTC",
        quiet_start: 0,
        quiet_end: 0,
      });
    });
    expect(saved).toBe(false);
    expect(result.current.uncertain).toBe(true);
  });
});
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
  it("distinguishes provider acceptance from recipient delivery and labels history", () => {
    const { rerender } = render(
      <WhatsAppConnection
        mode="ready"
        connection={{ ...disconnected, delivery: { state: "accepted", reason: null } }}
      />,
    );
    expect(screen.getByText(/Recipient delivery has not been confirmed/)).toBeTruthy();
    expect(screen.getByText(/may belong to a previous connection/)).toBeTruthy();
    rerender(
      <WhatsAppConnection
        mode="ready"
        connection={{ ...disconnected, delivery: { state: "unknown", reason: null } }}
      />,
    );
    expect(screen.getByText(/will not be resent automatically/)).toBeTruthy();
  });
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
