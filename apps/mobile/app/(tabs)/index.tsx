import { useCallback, useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, RefreshControl, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { listDocuments, search as searchApi, type DocumentOut, type SearchResult } from "../../src/lib/api";

const STATUS_COLORS: Record<string, string> = {
  ready: "#16a34a",
  pending: "#64748b",
  ocr_processing: "#d97706",
  embedding: "#d97706",
  failed: "#dc2626",
};

export default function Documents() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      setDocuments(await listDocuments());
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleSearch(text: string) {
    setQuery(text);
    if (!text.trim()) {
      setResults(null);
      return;
    }
    setResults(await searchApi(text.trim()));
  }

  const items = results !== null
    ? results.map((r) => ({ id: r.chunk_id, title: r.document_title, subtitle: r.content, docId: r.document_id, status: null as string | null }))
    : documents.map((d) => ({ id: d.id, title: d.title, subtitle: new Date(d.created_at).toLocaleString(), docId: d.id, status: d.status as string | null }));

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.search}
        placeholder="Search documents..."
        value={query}
        onChangeText={handleSearch}
      />
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => router.push(`/documents/${item.docId}`)}>
            <Text style={styles.rowTitle}>{item.title}</Text>
            <Text style={styles.rowSubtitle} numberOfLines={2}>{item.subtitle}</Text>
            {item.status && (
              <Text style={[styles.badge, { color: STATUS_COLORS[item.status] ?? "#64748b" }]}>{item.status}</Text>
            )}
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No documents yet.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  search: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 12 },
  row: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  rowTitle: { fontSize: 15, fontWeight: "500" },
  rowSubtitle: { fontSize: 13, color: "#64748b", marginTop: 2 },
  badge: { fontSize: 12, marginTop: 4 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
});
