import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { ApiError, getEntityGraph, type EntityGraphOut } from "../../src/lib/api";
import { EntityGraph } from "../../src/components/EntityGraph";

export default function EntityGraphScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [graph, setGraph] = useState<EntityGraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGraph(null);
    setError(null);
    getEntityGraph(id)
      .then(setGraph)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load graph"));
  }, [id]);

  if (error) return <View style={styles.container}><Text style={styles.error}>{error}</Text></View>;
  if (!graph) return <View style={styles.container}><ActivityIndicator /></View>;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>{graph.center.name}</Text>
      <Text style={styles.meta}>
        {graph.center.entity_type} · {graph.nodes.length} direct relationship{graph.nodes.length === 1 ? "" : "s"}
      </Text>
      {graph.nodes.length === 0 ? (
        <Text style={styles.empty}>No known relationships for this entity yet.</Text>
      ) : (
        <EntityGraph graph={graph} onSelectNode={(nodeId) => router.push(`/entities/${nodeId}`)} />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  title: { fontSize: 20, fontWeight: "600" },
  meta: { fontSize: 13, color: "#64748b", marginBottom: 12 },
  empty: { color: "#64748b", marginTop: 20 },
  error: { color: "#dc2626" },
});
