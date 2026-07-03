import { useState } from "react";
import { router } from "expo-router";
import { ActivityIndicator, FlatList, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { ApiError, chat, type ChatTurn, type Citation } from "../../src/lib/api";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
}

export default function Chat() {
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const message = input.trim();
    if (!message || sending) return;

    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const response = await chat(message, history);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, citations: response.citations }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat request failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={turns}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === "user" ? styles.userBubble : styles.assistantBubble]}>
            <Text style={item.role === "user" ? styles.userText : styles.assistantText}>{item.content}</Text>
            {item.citations?.map((c) => (
              <TouchableOpacity key={c.chunk_id} onPress={() => router.push(`/documents/${c.document_id}`)}>
                <Text style={styles.citation}>[{c.marker}] {c.document_title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>Ask a question about your documents.</Text>}
      />
      {sending && <ActivityIndicator style={styles.spinner} />}
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          placeholder="Ask a question..."
          value={input}
          onChangeText={setInput}
          editable={!sending}
        />
        <TouchableOpacity onPress={handleSend} disabled={sending || !input.trim()}>
          <Text style={styles.send}>Send</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  list: { gap: 8 },
  bubble: { padding: 10, borderRadius: 8, maxWidth: "85%" },
  userBubble: { backgroundColor: "#0f172a", alignSelf: "flex-end" },
  assistantBubble: { backgroundColor: "#f1f5f9", alignSelf: "flex-start" },
  userText: { color: "#fff" },
  assistantText: { color: "#0f172a" },
  citation: { fontSize: 12, color: "#2563eb", marginTop: 4 },
  empty: { textAlign: "center", color: "#64748b", marginTop: 40 },
  spinner: { marginVertical: 8 },
  error: { color: "#dc2626", marginBottom: 4 },
  inputRow: { flexDirection: "row", gap: 8, marginTop: 8, alignItems: "center" },
  input: { flex: 1, borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 10 },
  send: { color: "#2563eb", fontWeight: "600", padding: 8 },
});
