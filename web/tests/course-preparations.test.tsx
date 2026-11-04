import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { CoursePreparations } from "../components/course-preparations";
import { parsePreparations } from "../lib/preparations";
import { preparation } from "./preparation-fixture";

afterEach(cleanup);

it("shows limits, literal excerpts, gaps, unread content and questions without work actions", () => {
  const p = preparation();
  p.excerpts[0].quote = '<img src="x" onerror="send()"> Read the manual.';
  const view = render(<CoursePreparations records={parsePreparations([p])} />);
  expect(screen.getByText(p.notice)).toBeTruthy();
  expect(screen.getByText(p.excerpts[0].quote)).toBeTruthy();
  expect(view.container.querySelector("img")).toBeNull();
  expect(screen.getByText("linked content unread")).toBeTruthy();
  expect(screen.getByText("More original content remains unread.")).toBeTruthy();
  expect(screen.getByText(p.questions[0])).toBeTruthy();
  expect(screen.getByText("Current limited evidence")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /accept|draft|send|download/i })).toBeNull();
  expect(view.container.querySelector("form, a, input, textarea")).toBeNull();
});

it("retains historical excerpts with a visible warning instead of current readiness", () => {
  const p = { ...preparation(), current: false };
  render(<CoursePreparations records={parsePreparations([p])} />);
  expect(screen.getByText("Historical checklist")).toBeTruthy();
  expect(screen.getByText(/This checklist is historical/)).toBeTruthy();
  expect(screen.getByText(p.excerpts[0].quote)).toBeTruthy();
  expect(screen.queryByText("Current limited evidence")).toBeNull();
});

it("supports an older missing field and a bounded empty state", () => {
  expect(parsePreparations(undefined)).toEqual([]);
  expect(parsePreparations([])).toEqual([]);
  const view = render(<CoursePreparations records={[]} />);
  expect(view.container.textContent).toBe("");
});

it.each([
  (p: any) => {
    p.current = "true";
  },
  (p: any) => {
    p.kind = "checked_artifact";
  },
  (p: any) => {
    p.notice = "";
  },
  (p: any) => {
    p.created_at = "not a date";
  },
  (p: any) => {
    p.excerpts[0].quote = "x".repeat(1501);
  },
  (p: any) => {
    p.excerpts[0].object_id = "00000000-0000-4000-8000-000000000099";
  },
  (p: any) => {
    p.evidence[0].unread_continuation = null;
  },
  (p: any) => {
    p.evidence[0].version_id = "not a source version";
  },
  (p: any) => {
    p.evidence = [];
  },
  (p: any) => {
    p.questions = Array(6).fill("Question");
  },
])("rejects malformed or unbound projection data", (change) => {
  const p = preparation();
  change(p);
  expect(() => parsePreparations([p])).toThrow("Preparation information unavailable");
});

it("rejects duplicate records and over-limit history", () => {
  expect(() => parsePreparations([preparation(), preparation()])).toThrow();
  expect(() => parsePreparations(Array(21).fill(preparation()))).toThrow();
});
