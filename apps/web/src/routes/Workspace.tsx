import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useTranslation } from "react-i18next";
import {
  listDocuments,
  listCategories,
  listWorkspacesSharedWithMe,
  search as searchApi,
  deleteDocument,
  downloadDocumentsCsv,
  getDocument,
  ApiError,
  type DocumentDetailOut,
  type DocumentOut,
  type CategoryOut,
  type SearchResult,
  type WorkspaceMemberOut,
} from "../lib/api";
import UploadDialog from "../components/UploadDialog";
import { ActivityTab } from "../components/ActivityTab";
import { CategoryFilterGrid } from "../components/CategoryFilterGrid";
import { DataTable, type Column } from "../components/ui/DataTable";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { DeleteConfirmButton } from "../components/DeleteConfirmButton";
import { DocumentDetailContent } from "../components/DocumentDetailContent";
import { Drawer } from "../components/ui/Drawer";
import { ShareButton } from "../components/ShareButton";
import { TextField } from "../components/ui/form";
import EmptyState from "../components/EmptyState";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { BulkActionBar } from "../components/ui/BulkActionBar";
import { FilterChips } from "../components/ui/FilterChips";
import { SkeletonLines } from "../components/ui/Skeleton";
import { useToast } from "../lib/toast";
import { useDateFormat } from "../hooks/useDateFormat";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

export default function Workspace() {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetailOut | null>(null);
  const [deleting, setDeleting] = useState(false);
  const STATUS_FILTER_OPTIONS = [
    { id: "ready", label: t("documents.filterReady") },
    { id: "failed", label: t("documents.filterFailed") },
    { id: "pending", label: t("documents.filterPending") },
  ];
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [categoryFilters, setCategoryFilters] = useState<string[]>([]);
  const { isSelected, toggle, clear, selectedCount, selectedKeys } = useBulkSelection<DocumentOut>((doc) => doc.id);
  const { showToast } = useToast();
  const [exporting, setExporting] = useState(false);
  const [sharedWorkspaces, setSharedWorkspaces] = useState<WorkspaceMemberOut[]>([]);
  const [viewedOwnerId, setViewedOwnerId] = useState<string | null>(null);
  const viewingSharedWorkspace = viewedOwnerId !== null;
  const activeSharedWorkspace = sharedWorkspaces.find((w) => w.owner_id === viewedOwnerId);

  const refresh = useCallback(
    (showLoading = false) => {
      if (showLoading) setLoading(true);
      listDocuments(viewedOwnerId ?? undefined)
        .then(setDocuments)
        .finally(() => setLoading(false));
    },
    [viewedOwnerId]
  );

  useEffect(() => {
    refresh(true);
    const interval = setInterval(() => refresh(false), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    listCategories().then(setCategories);
  }, []);

  useEffect(() => {
    listWorkspacesSharedWithMe().then(setSharedWorkspaces).catch(() => {});
  }, []);

  const loadSelected = useCallback(() => {
    if (!id) return;
    getDocument(id).then(setSelectedDocument).catch(() => setSelectedDocument(null));
  }, [id]);

  useEffect(() => {
    setSelectedDocument(null);
    loadSelected();
  }, [loadSelected]);

  async function handleDrawerDelete() {
    if (!id || !selectedDocument) return;
    setDeleting(true);
    try {
      await deleteDocument(id);
      showToast(t("documentDetail.deletedToast", { title: selectedDocument.title }));
      navigate("/documents");
      refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : t("documentDetail.deleteError"));
    } finally {
      setDeleting(false);
    }
  }

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setSearching(true);
    try {
      setResults(await searchApi(query.trim()));
    } finally {
      setSearching(false);
    }
  }

  async function handleBulkDelete() {
    const ids = [...selectedKeys];
    await Promise.all(ids.map((id) => deleteDocument(id)));
    clear();
    refresh();
    showToast(t("documents.deletedToast", { count: ids.length }));
  }

  async function handleExportCsv() {
    setExporting(true);
    try {
      await downloadDocumentsCsv(viewedOwnerId ?? undefined);
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : t("documents.exportError"));
    } finally {
      setExporting(false);
    }
  }

  const activeFilters = useMemo(() => new Set(statusFilters), [statusFilters]);
  const activeCategoryFilters = useMemo(() => new Set(categoryFilters), [categoryFilters]);
  const filteredDocuments = useMemo(
    () =>
      documents.filter(
        (doc) =>
          (activeFilters.size === 0 || activeFilters.has(doc.status)) &&
          (activeCategoryFilters.size === 0 || (doc.category_id !== null && activeCategoryFilters.has(doc.category_id)))
      ),
    [documents, activeFilters, activeCategoryFilters]
  );

  const columns: Column<DocumentOut>[] = [
    ...(viewingSharedWorkspace
      ? []
      : [
          {
            key: "select",
            header: "",
            render: (doc: DocumentOut) => (
              <input
                type="checkbox"
                checked={isSelected(doc)}
                onChange={() => toggle(doc)}
                onClick={(event) => event.stopPropagation()}
                className="h-4 w-4 accent-accent"
              />
            ),
          },
        ]),
    {
      key: "title",
      header: t("documents.columnTitle"),
      sortable: true,
      sortValue: (doc) => doc.title.toLowerCase(),
      render: (doc) => (
        <Link to={`/documents/${doc.id}`} className="font-medium text-ink hover:text-accent">
          {doc.title}
        </Link>
      ),
    },
    {
      key: "created_at",
      header: t("documents.columnUploaded"),
      sortable: true,
      sortValue: (doc) => doc.created_at,
      render: (doc) => formatDateTime(doc.created_at),
    },
    {
      key: "status",
      header: t("documents.columnStatus"),
      render: (doc) => <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge>,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-ink">{t("documents.title")}</h1>
          {sharedWorkspaces.length > 0 && (
            <select
              value={viewedOwnerId ?? "self"}
              onChange={(e) => setViewedOwnerId(e.target.value === "self" ? null : e.target.value)}
              aria-label={t("documents.viewingWorkspace")}
              className="rounded-lg border border-edge bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-accent"
            >
              <option value="self">{t("documents.viewingMyOwn")}</option>
              {sharedWorkspaces.map((w) => (
                <option key={w.owner_id} value={w.owner_id}>
                  {t("documents.viewingSharedBy", { name: w.owner_display_name })}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(!viewingSharedWorkspace || activeSharedWorkspace?.can_export) && (
            <Button variant="secondary" onClick={handleExportCsv} disabled={exporting}>
              {t("documents.exportCsv")}
            </Button>
          )}
          {!viewingSharedWorkspace && <UploadDialog onUploaded={refresh} />}
        </div>
      </div>

      <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1">
          <TextField
            label={t("documents.searchLabel")}
            value={query}
            onChange={setQuery}
            placeholder={t("documents.searchPlaceholder")}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="secondary" disabled={searching}>
            {t("documents.searchButton")}
          </Button>
          {results !== null && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setResults(null);
                setQuery("");
              }}
            >
              {t("documents.clearButton")}
            </Button>
          )}
        </div>
      </form>

      {results !== null ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-ink-2">{t("documents.results", { count: results.length })}</h2>
          {results.map((r) => (
            <Link
              key={r.chunk_id}
              to={`/documents/${r.document_id}`}
              className="block rounded-2xl border border-edge bg-surface p-4 shadow-raised hover:border-accent"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{r.document_title}</span>
                <span className="text-xs text-ink-3">score {r.score.toFixed(3)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-ink-2">{r.content}</p>
            </Link>
          ))}
        </div>
      ) : loading ? (
        <SkeletonLines />
      ) : documents.length === 0 ? (
        <EmptyState message={t("documents.emptyMessage")} />
      ) : (
        <>
          <FilterChips
            label={t("documents.statusFilterLabel")}
            chips={STATUS_FILTER_OPTIONS.filter((opt) => statusFilters.includes(opt.id))}
            onRemove={(id) => setStatusFilters((prev) => prev.filter((s) => s !== id))}
            addOptions={STATUS_FILTER_OPTIONS.filter((opt) => !statusFilters.includes(opt.id))}
            onAdd={(opt) => setStatusFilters((prev) => [...prev, opt.id])}
          />
          {categories.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-ink-3">{t("documents.categoryFilterLabel")}</p>
              <CategoryFilterGrid
                categories={categories}
                activeIds={activeCategoryFilters}
                onToggleGroup={(childIds) => {
                  const allActive = childIds.every((id) => activeCategoryFilters.has(id));
                  setCategoryFilters((prev) =>
                    allActive
                      ? prev.filter((id) => !childIds.includes(id))
                      : [...new Set([...prev, ...childIds])]
                  );
                }}
                onToggleChild={(id) =>
                  setCategoryFilters((prev) => (prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]))
                }
              />
            </div>
          )}
          <DataTable columns={columns} rows={filteredDocuments} rowKey={(doc) => doc.id} />
          <BulkActionBar
            count={selectedCount}
            onCancel={clear}
            actions={[{ label: t("documents.deleteAction"), onClick: handleBulkDelete, variant: "danger" }]}
          />
        </>
      )}

      <Drawer
        open={!!id}
        onClose={() => navigate("/documents")}
        title={selectedDocument?.title ?? ""}
        tabs={[
          {
            id: "details",
            label: t("drawer.details"),
            content: selectedDocument ? (
              <DocumentDetailContent document={selectedDocument} onChanged={loadSelected} />
            ) : (
              <SkeletonLines />
            ),
          },
          {
            id: "activity",
            label: t("drawer.activity"),
            content: id ? <ActivityTab entityType="document" entityId={id} /> : null,
          },
        ]}
        footer={
          id && (
            <>
              <ShareButton entityType="document" entityId={id} />
              <DeleteConfirmButton
                confirmTitle={t("documentDetail.deleteModalTitle", { title: selectedDocument?.title ?? "" })}
                confirmBody={t("documentDetail.deleteModalBody")}
                confirmLabel={t("documentDetail.deleteConfirm")}
                onConfirm={handleDrawerDelete}
                deleting={deleting}
              />
            </>
          )
        }
      />
    </div>
  );
}
