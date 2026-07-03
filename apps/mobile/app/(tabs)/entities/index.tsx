import { useEffect, useState } from "react";
import { router } from "expo-router";
import { FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { listEntities, type EntityOut } from "../../../src/lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
};

const TYPES = ["", "person", "organization", "location", "other"];

export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");

  useEffect(() => {
    listEntities(q || undefined, entityType || undefined).then(setEntities);
  }, [q, entityType]);

  return (
    <View style={styles.container}>
      <TextInput style={styles.search} placeholder="Search entities..." value={q} onChangeText={setQ} />
      <View style={styles.typeRow}>
        {TYPES.map((t) => (
          <TouchableOpacity key={t || "all"} onPress={() => setEntityType(t)}>
            <Text style={[styles.typeLabel, entityType === t && styles.typeLabelActive]}>{t || "all"}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <FlatList
        data={entities}
        keyExtractor={(e) => e.id}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.row} onPress={() => router.push(`/entities/${item.id}`)}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={[styles.badge, { color: TYPE_COLORS[item.entity_type] ?? TYPE_COLORS.other }]}>
              {item.entity_type}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No entities found.</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  search: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10, marginBottom: 8 },
  typeRow: { flexDirection: "row", gap: 12, marginBottom: 12, flexWrap: "wrap" },
  typeLabel: { color: "#64748b", textTransform: "capitalize" },
  typeLabelActive: { color: "#0f172a", fontWeight: "600" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  name: { fontSize: 15, fontWeight: "500" },
  badge: { fontSize: 12 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
});
