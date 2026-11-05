// app shell: plain state navigation between home, the reader and vocab.
import { useState } from 'react';
import {
  LogBox,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  useColorScheme,
  View,
} from 'react-native';
import type { Article, SampleFile } from './src/types';
import { fonts, usePalette } from './src/theme';
import samples from './src/data/samples.json';
import ReaderScreen from './src/reader/ReaderScreen';
import { useVocab } from './src/vocab/store';
import VocabScreen from './src/vocab/VocabScreen';

// react native's SafeAreaView is deprecated in favour of a package we are not adding.
// it still works on ios, so silence the one-time dev warning.
LogBox.ignoreLogs(['SafeAreaView has been deprecated']);

const articles = (samples as SampleFile).articles;

type Screen = { name: 'home' } | { name: 'reader'; articleId: string } | { name: 'vocab' };

export default function App() {
  const palette = usePalette();
  const scheme = useColorScheme();
  const [screen, setScreen] = useState<Screen>({ name: 'home' });
  const goHome = () => setScreen({ name: 'home' });
  const article = screen.name === 'reader' ? articles.find((a) => a.id === screen.articleId) : undefined;

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: palette.bg }]}>
      <StatusBar barStyle={scheme === 'dark' ? 'light-content' : 'dark-content'} />
      {screen.name === 'vocab' ? (
        <VocabScreen onBack={goHome} />
      ) : article ? (
        <ReaderScreen key={article.id} article={article} onBack={goHome} />
      ) : (
        <HomeScreen
          onOpen={(a) => setScreen({ name: 'reader', articleId: a.id })}
          onVocab={() => setScreen({ name: 'vocab' })}
        />
      )}
    </SafeAreaView>
  );
}

type HomeProps = { onOpen: (article: Article) => void; onVocab: () => void };

function HomeScreen({ onOpen, onVocab }: HomeProps) {
  const palette = usePalette();
  const { dueCount } = useVocab();
  const [today, ...earlier] = articles;
  const date = new Date()
    .toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
    .toLowerCase();
  const sans = { fontFamily: fonts.sans };
  const serif = { fontFamily: fonts.serif };

  return (
    <ScrollView contentContainerStyle={styles.scroll}>
      <View style={styles.column}>
        <Text style={[styles.date, sans, { color: palette.muted }]}>{date}</Text>

        {today ? (
          <Pressable onPress={() => onOpen(today)} accessibilityRole="button" style={styles.today}>
            <Text style={[styles.meta, sans, { color: palette.muted }]}>
              {today.source} · {today.read_minutes} min
            </Text>
            <Text style={[styles.title, serif, { color: palette.ink }]}>{today.title}</Text>
            <Text style={[styles.read, sans, { color: palette.accent }]}>read</Text>
          </Pressable>
        ) : (
          <Text style={[styles.title, serif, { color: palette.muted }]}>no article today</Text>
        )}

        <Pressable onPress={onVocab} accessibilityRole="button" style={styles.vocab}>
          <Text style={[styles.vocabText, sans, { color: palette.muted }]}>vocab · {dueCount} due</Text>
        </Pressable>

        {earlier.length > 0 && (
          <View style={[styles.earlier, { borderTopColor: palette.rule }]}>
            <Text style={[styles.meta, sans, { color: palette.muted }]}>earlier samples</Text>
            {earlier.map((a) => (
              <Pressable key={a.id} onPress={() => onOpen(a)} accessibilityRole="button" style={styles.earlierItem}>
                <Text style={[styles.earlierTitle, serif, { color: palette.muted }]}>{a.title}</Text>
                <Text style={[styles.earlierMeta, sans, { color: palette.muted }]}>
                  {a.source} · {a.read_minutes} min
                </Text>
              </Pressable>
            ))}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  // SafeAreaView only pads on ios; android draws edge to edge under the status bar.
  safe: { flex: 1, paddingTop: Platform.OS === 'android' ? StatusBar.currentHeight : 0 },
  scroll: { paddingHorizontal: 24, paddingTop: 56, paddingBottom: 64 },
  column: { width: '100%', maxWidth: 640, alignSelf: 'center' },
  date: { fontSize: 14, marginBottom: 56 },
  today: { marginBottom: 48 },
  meta: { fontSize: 12, letterSpacing: 1.4, textTransform: 'uppercase' },
  title: { fontSize: 34, lineHeight: 42, marginTop: 12 },
  read: { fontSize: 15, marginTop: 20 },
  vocab: { alignSelf: 'flex-start', paddingVertical: 8, marginBottom: 72 },
  vocabText: { fontSize: 15 },
  earlier: { borderTopWidth: StyleSheet.hairlineWidth, paddingTop: 24 },
  earlierItem: { paddingVertical: 14 },
  earlierTitle: { fontSize: 18, lineHeight: 25 },
  earlierMeta: { fontSize: 12, marginTop: 4 },
});
