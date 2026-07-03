import { useCallback, useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, StyleSheet, Switch, Text, TouchableOpacity, View } from "react-native";
import { ApiError, listTasks, updateTaskStatus, type TaskOut } from "../../src/lib/api";

type Filter = "open" | "done" | "all";

export default function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((f: Filter) => {
    listTasks(f === "all" ? undefined : f)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load tasks"));
  }, []);

  useEffect(() => {
    refresh(filter);
  }, [filter, refresh]);

  async function toggle(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.filterRow}>
        {(["open", "done", "all"] as Filter[]).map((f) => (
          <TouchableOpacity key={f} onPress={() => setFilter(f)}>
            <Text style={[styles.filterLabel, filter === f && styles.filterLabelActive]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={tasks}
        keyExtractor={(t) => t.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Switch value={item.status === "done"} onValueChange={() => toggle(item)} />
            <View style={styles.rowText}>
              <Text style={item.status === "done" ? styles.doneTitle : styles.title}>{item.title}</Text>
              {item.description && <Text style={styles.description}>{item.description}</Text>}
              {item.document_id && (
                <TouchableOpacity onPress={() => router.push(`/documents/${item.document_id}`)}>
                  <Text style={styles.link}>Source document</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No {filter !== "all" ? filter : ""} tasks.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  filterRow: { flexDirection: "row", gap: 16, marginBottom: 12 },
  filterLabel: { color: "#64748b", textTransform: "capitalize" },
  filterLabelActive: { color: "#0f172a", fontWeight: "600" },
  row: { flexDirection: "row", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  rowText: { flex: 1, gap: 2 },
  title: { fontSize: 15, fontWeight: "500" },
  doneTitle: { fontSize: 15, color: "#94a3b8", textDecorationLine: "line-through" },
  description: { fontSize: 13, color: "#64748b" },
  link: { fontSize: 12, color: "#2563eb" },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
  error: { color: "#dc2626", marginBottom: 8 },
});
