export type Agent = { id: string; user_id: string; paused: boolean };
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
export type Task = {
  id: string;
  status: "ready" | "running" | "done" | "blocked";
  last_error?: string | null;
};
export type Submission = { key: string; content: string };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/agent/${path}`, {
    ...options,
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      typeof data.detail === "string" ? data.detail : "Please try again.",
    );
  return data as T;
}

export function submitMessage(submission: Submission, signal?: AbortSignal) {
  return api<{ task_id: string; status: Task["status"] }>("messages", {
    method: "POST",
    body: JSON.stringify({ content: submission.content }),
    headers: { "Idempotency-Key": submission.key },
    signal,
  });
}
