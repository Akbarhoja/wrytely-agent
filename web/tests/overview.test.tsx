import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { Overview } from "../components/overview";
import type { WorkItem } from "../lib/client";

afterEach(cleanup);
const props = {
  loaded: true,
  loading: false,
  signedIn: true,
  paused: false,
  configured: false,
  error: false,
  onConversation: vi.fn(),
  onConnections: vi.fn(),
  onRefresh: vi.fn(),
};
it("groups actual saved tasks without inventing decision requests", () => {
  const work = ["ready", "running", "blocked", "done"].map((status, index) => ({
    id: String(index),
    status,
    title: `Saved request ${index}`,
    attempts: 1,
    created_at: "2026-10-28T00:00:00Z",
  })) as WorkItem[];
  render(<Overview {...props} work={work} />);
  const active = within(screen.getByRole("region", { name: "In motion" }));
  expect(active.getByText("Saved request 0")).toBeTruthy();
  expect(active.getByText("Saved request 1")).toBeTruthy();
  expect(active.queryByText("Saved request 2")).toBeNull();
  const blocked = within(screen.getByRole("region", { name: "Needs attention" }));
  expect(blocked.getByText("Saved request 2")).toBeTruthy();
  expect(
    within(screen.getByRole("region", { name: "Completed" })).getByText("Saved request 3"),
  ).toBeTruthy();
  expect(screen.getByText("Decision requests are not connected yet")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Approve|Submit assignment/ })).toBeNull();
  fireEvent.click(active.getByRole("button", { name: /Open conversation for Saved request 0/ }));
  expect(props.onConversation).toHaveBeenCalled();
});
it("distinguishes unloaded work from an empty verified account", () => {
  render(<Overview {...props} loaded={false} work={[]} />);
  expect(screen.getAllByLabelText("Not loaded")).toHaveLength(3);
  expect(screen.queryByText("No blocked work.")).toBeNull();
});
it("shows a read failure instead of implying there is no work", () => {
  render(<Overview {...props} loaded={false} error work={[]} />);
  expect(screen.getAllByText("Work is unavailable.")).toHaveLength(3);
  expect(screen.getByText("Connection needs attention")).toBeTruthy();
});
