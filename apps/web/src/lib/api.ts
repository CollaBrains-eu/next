// Default to same-origin (relative paths) -- correct for the production build,
// where Caddy reverse-proxies API paths on the same domain the SPA is served
// from. Local dev overrides this via apps/web/.env.development.
const API_URL = import.meta.env.VITE_API_URL ?? "";

const TOKEN_KEY = "collabrains_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
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
  phone_prompt_dismissed: boolean;
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

export function linkPhoneNumber(phoneNumber: string): Promise<UserOut> {
  return request<UserOut>("/auth/me/phone", {
    method: "PUT",
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}

export function dismissPhonePrompt(): Promise<UserOut> {
  return request<UserOut>("/auth/me/dismiss-phone-prompt", { method: "PATCH" });
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
  category_id: string | null;
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

export function deleteDocument(id: string): Promise<void> {
  return request<void>(`/documents/${id}`, { method: "DELETE" });
}

export function uploadDocument(file: File): Promise<DocumentOut> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentOut>("/documents", { method: "POST", body: form });
}

export function summarizeDocument(id: string): Promise<{ summary: string }> {
  return request<{ summary: string }>(`/documents/${id}/summarize`, { method: "POST" });
}

export interface CategoryOut {
  id: string;
  slug: string;
  icon: string | null;
  color: string | null;
  parent_id: string | null;
}

export function listCategories(categoryType = "document"): Promise<CategoryOut[]> {
  return request<CategoryOut[]>(`/categories?category_type=${categoryType}`);
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

export interface DraftResponse {
  draft: string;
  citations: Citation[];
  disclaimer: string;
}

export function legalDraft(instruction: string, documentIds: string[]): Promise<DraftResponse> {
  return request<DraftResponse>("/legal/draft", {
    method: "POST",
    body: JSON.stringify({ instruction, document_ids: documentIds }),
  });
}

export type TaskStatus = "open" | "in_progress" | "done";

export interface TaskOut {
  id: string;
  document_id: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  assignee: string | null;
  status: string;
  position: number;
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

export function moveTask(id: string, status: TaskStatus, position: number): Promise<TaskOut> {
  return request<TaskOut>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status, position }),
  });
}

export interface EntityOut {
  id: string;
  name: string;
  entity_type: string;
  status: string;
  created_at: string;
}

export function listEntities(q?: string, entityType?: string, status?: string): Promise<EntityOut[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (entityType) params.set("entity_type", entityType);
  if (status) params.set("status", status);
  const query = params.toString();
  return request<EntityOut[]>(`/entities${query ? `?${query}` : ""}`);
}

export function approveEntity(id: string): Promise<EntityOut> {
  return request<EntityOut>(`/entities/${id}/approve`, { method: "POST" });
}

export function rejectEntity(id: string): Promise<EntityOut> {
  return request<EntityOut>(`/entities/${id}/reject`, { method: "POST" });
}

export interface BulkReviewItem {
  entity_id: string;
  action: "approve" | "reject";
}

export function bulkReviewEntities(items: BulkReviewItem[]): Promise<EntityOut[]> {
  return request<EntityOut[]>("/entities/bulk-review", {
    method: "POST",
    body: JSON.stringify(items),
  });
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

export interface CaseOut {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
}

export interface CaseDashboardOut extends CaseOut {
  documents: { id: string; title: string }[];
  tasks: { id: string; title: string; status: string }[];
  decisions: { id: string; summary: string }[];
  vehicles: { id: string; kenteken: string | null; merk: string | null; handelsbenaming: string | null }[];
}

export interface DecisionListItemOut {
  id: string;
  summary: string;
}

export function listCases(): Promise<CaseOut[]> {
  return request<CaseOut[]>("/cases");
}

export function createCase(name: string, description?: string): Promise<CaseOut> {
  return request<CaseOut>("/cases", {
    method: "POST",
    body: JSON.stringify({ name, description: description || null }),
  });
}

export function getCase(id: string): Promise<CaseDashboardOut> {
  return request<CaseDashboardOut>(`/cases/${id}`);
}

export function updateCaseStatus(id: string, status: "open" | "closed"): Promise<CaseOut> {
  return request<CaseOut>(`/cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function listDecisions(): Promise<DecisionListItemOut[]> {
  return request<DecisionListItemOut[]>("/decisions");
}

export function attachDocumentToCase(documentId: string, caseId: string | null): Promise<{ id: string; title: string }> {
  return request<{ id: string; title: string }>(`/documents/${documentId}/case`, {
    method: "PUT",
    body: JSON.stringify({ case_id: caseId }),
  });
}

export function linkTaskToCase(caseId: string, taskId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/tasks/${taskId}`, { method: "POST" });
}

export function linkDecisionToCase(caseId: string, decisionId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/decisions/${decisionId}`, { method: "POST" });
}

export interface VehicleOut {
  id: string;
  kenteken: string | null;
  vin: string | null;
  voertuigsoort: string | null;
  merk: string | null;
  handelsbenaming: string | null;
  eerste_kleur: string | null;
  datum_eerste_toelating: string | null;
  vervaldatum_apk: string | null;
  wam_verzekerd: string | null;
  openstaande_terugroepactie_indicator: string | null;
  brandstofomschrijving: string | null;
  fetched_at: string | null;
  created_at: string;
}

export function listVehicles(): Promise<VehicleOut[]> {
  return request<VehicleOut[]>("/vehicles");
}

export function lookupVehicle(kenteken: string): Promise<VehicleOut> {
  return request<VehicleOut>("/vehicles/lookup", {
    method: "POST",
    body: JSON.stringify({ kenteken }),
  });
}

export function linkVehicleToCase(caseId: string, vehicleId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/vehicles/${vehicleId}`, { method: "POST" });
}

export interface AskResponse {
  answer: string;
  tools_called: string[];
}

export function askManager(message: string): Promise<AskResponse> {
  return request<AskResponse>("/manager/ask", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export interface PreferencesOut {
  preferred_language: string | null;
}

export function getPreferences(): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me");
}

export function setPreferences(preferredLanguage: string | null): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me", {
    method: "PUT",
    body: JSON.stringify({ preferred_language: preferredLanguage }),
  });
}

export interface AdminStatsOut {
  total_users: number;
  total_documents: number;
  documents_by_status: Record<string, number>;
  ai_calls_last_24h: number;
}

export function getAdminStats(): Promise<AdminStatsOut> {
  return request<AdminStatsOut>("/admin/stats");
}

export interface AiUsageRowOut {
  key: string;
  call_count: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
}

export function getAdminAiUsage(groupBy: "user" | "model" | "endpoint" = "model"): Promise<AiUsageRowOut[]> {
  return request<AiUsageRowOut[]>(`/admin/ai-usage?group_by=${groupBy}`);
}

export interface ServiceHealthOut {
  name: string;
  status: "up" | "down";
  detail: string | null;
}

export function getAdminHealth(): Promise<ServiceHealthOut[]> {
  return request<ServiceHealthOut[]>("/admin/health");
}

export interface BugReportOut {
  id: string;
  user_id: string;
  description: string;
  status: string;
  ai_analysis: string | null;
  created_at: string;
}

export function listBugReports(statusFilter?: string): Promise<BugReportOut[]> {
  const query = statusFilter ? `?status_filter=${statusFilter}` : "";
  return request<BugReportOut[]>(`/admin/bug-reports${query}`);
}

export function analyzeBugReport(id: string): Promise<BugReportOut> {
  return request<BugReportOut>(`/admin/bug-reports/${id}/analyze`, { method: "POST" });
}

export interface AdminUserCreateInput {
  username: string;
  display_name: string;
  email: string;
  is_admin: boolean;
  phone_number?: string | null;
}

export interface AdminUserCreatedOut {
  username: string;
  temporary_password: string;
}

export function createAdminUser(input: AdminUserCreateInput): Promise<AdminUserCreatedOut> {
  return request<AdminUserCreatedOut>("/admin/users", { method: "POST", body: JSON.stringify(input) });
}

export interface AdminUserOut {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
  created_at: string;
  last_login_at: string | null;
}

export function listAdminUsers(limit?: number, offset?: number): Promise<AdminUserOut[]> {
  const params = new URLSearchParams();
  if (limit !== undefined) params.set("limit", String(limit));
  if (offset !== undefined) params.set("offset", String(offset));
  const query = params.toString();
  return request<AdminUserOut[]>(`/admin/users${query ? `?${query}` : ""}`);
}

export interface AddressOut {
  id: string;
  name: string;
  street: string | null;
  house_number: string | null;
  postal_code: string | null;
  city: string | null;
  country: string | null;
}

export interface ResidencyOut {
  id: string;
  address: AddressOut;
  valid_from: string | null;
  valid_to: string | null;
  status: string;
  source_document_id: string | null;
  linked_document_count: number;
  created_at: string;
}

export function listMyResidencies(): Promise<ResidencyOut[]> {
  return request<ResidencyOut[]>("/users/me/residencies");
}

export function listUserResidencies(userId: string): Promise<ResidencyOut[]> {
  return request<ResidencyOut[]>(`/admin/users/${userId}/residencies`);
}

export function approveResidency(id: string): Promise<ResidencyOut> {
  return request<ResidencyOut>(`/residencies/${id}/approve`, { method: "POST" });
}

export function rejectResidency(id: string): Promise<ResidencyOut> {
  return request<ResidencyOut>(`/residencies/${id}/reject`, { method: "POST" });
}

export function correctResidency(
  id: string, input: { valid_from?: string; valid_to?: string }
): Promise<ResidencyOut> {
  return request<ResidencyOut>(`/residencies/${id}`, { method: "PATCH", body: JSON.stringify(input) });
}
