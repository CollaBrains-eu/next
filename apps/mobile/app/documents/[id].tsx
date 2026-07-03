import { useEffect, useState } from "react";
import { useLocalSearchParams } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { ApiError, getDocument, type DocumentDetailOut } from "../../src/lib/api";

export default function DocumentDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load document"));
  }, [id]);

  if (error) return <View style={styles.container}><Text style={styles.error}>{error}</Text></View>;
  if (!doc) return <View style={styles.container}><ActivityIndicator /></View>;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{doc.title}</Text>
      <Text style={styles.meta}>{doc.mime_type} · {doc.status} · {doc.chunk_count} chunk(s)</Text>
      {doc.summary && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary</Text>
          <Text>{doc.summary}</Text>
        </View>
      )}
      {doc.ocr_text && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Extracted text</Text>
          <Text>{doc.ocr_text}</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  content: { gap: 12 },
  title: { fontSize: 20, fontWeight: "600" },
  meta: { fontSize: 13, color: "#64748b" },
  section: { marginTop: 8, gap: 4 },
  sectionTitle: { fontSize: 14, fontWeight: "600", color: "#64748b" },
  error: { color: "#dc2626" },
});
