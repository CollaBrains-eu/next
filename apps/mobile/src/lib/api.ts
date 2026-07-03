import * as SecureStore from "expo-secure-store";

const API_URL = "https://v78281.1blu.de";
const TOKEN_KEY = "collabrains_token";

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface UserOut {
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
}

export async function login(username: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username, password });
  const result = await request<{ access_token: string; token_type: string }>("/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  return result.access_token;
}

export function fetchMe(): Promise<UserOut> {
  return request<UserOut>("/auth/me");
}

export interface DocumentOut {
  id: string;
  title: string;
  filename: string;
  mime_type: string;
  status: string;
  error: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DocumentDetailOut extends DocumentOut {
  ocr_text: string | null;
  chunk_count: number;
  summary: string | null;
}

export function listDocuments(): Promise<DocumentOut[]> {
  return request<DocumentOut[]>("/documents");
}

export function getDocument(id: string): Promise<DocumentDetailOut> {
  return request<DocumentDetailOut>(`/documents/${id}`);
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
}

export function search(query: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
}

export interface Citation {
  marker: number;
  document_id: string;
  document_title: string;
  chunk_id: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
}

export function chat(message: string, history: ChatTurn[]): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export interface TaskOut {
  id: string;
  document_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  assignee: string | null;
  status: string;
  source: string;
  created_at: string;
}

export function listTasks(statusFilter?: string): Promise<TaskOut[]> {
  const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
  return request<TaskOut[]>(`/tasks${query}`);
}

export function updateTaskStatus(id: string, status: "open" | "done"): Promise<TaskOut> {
  return request<TaskOut>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export interface EntityOut {
  id: string;
  name: string;
  entity_type: string;
  created_at: string;
}

export function listEntities(q?: string, entityType?: string): Promise<EntityOut[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (entityType) params.set("entity_type", entityType);
  const query = params.toString();
  return request<EntityOut[]>(`/entities${query ? `?${query}` : ""}`);
}

export interface GraphNode {
  id: string;
  name: string;
  entity_type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship_type: string;
  document_id: string | null;
}

export interface EntityGraphOut {
  center: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function getEntityGraph(id: string): Promise<EntityGraphOut> {
  return request<EntityGraphOut>(`/entities/${id}/graph`);
}
