// one article, read calmly. tap a word to save it (with its sentence) to vocab.
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import type { Article } from '../types';
import { fonts, usePalette, type Palette } from '../theme';
import { sentenceAt, tokenize, type Token } from '../lib/text';
import { useVocab } from '../vocab/store';

type Selection = { paragraph: number; start: number; word: string; sentence: string };
type Status = 'idle' | 'saving' | 'saved' | 'error';

type Props = { article: Article; onBack: () => void };

export default function ReaderScreen({ article, onBack }: Props) {
  const palette = usePalette();
  const { words, saveWord } = useVocab();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  // the latest selection, so a save that finishes late can tell if the user moved on.
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  const paragraphs = useMemo(() => article.paragraphs.map(tokenize), [article]);
  const savedHere = useMemo(
    () => new Set(words.filter((w) => w.articleId === article.id).map((w) => w.word.toLowerCase())),
    [words, article.id],
  );
  // the store dedupes across all articles, so a word saved elsewhere cannot be saved again.
  const alreadySaved = selection !== null && words.some((w) => w.word.toLowerCase() === selection.word.toLowerCase());

  const onWordPress = useCallback(
    (paragraph: number, token: Token) => {
      setStatus('idle');
      setSelection((current) =>
        current?.paragraph === paragraph && current.start === token.start
          ? null
          : { paragraph, start: token.start, word: token.text, sentence: sentenceAt(article.paragraphs[paragraph], token.start) },
      );
    },
    [article],
  );

  // after a save, show 'saved' briefly, then let the page go quiet again.
  useEffect(() => {
    if (status !== 'saved') return;
    const timer = setTimeout(() => {
      setSelection(null);
      setStatus('idle');
    }, 1200);
    return () => clearTimeout(timer);
  }, [status]);

  async function save() {
    const saving = selection;
    if (!saving) return;
    setStatus('saving');
    let next: Status = 'saved';
    try {
      await saveWord({
        word: saving.word,
        sentence: saving.sentence,
        articleId: article.id,
        articleTitle: article.title,
        source: article.source,
      });
    } catch (e) {
      console.warn('reader: could not save word', e);
      next = 'error';
    }
    if (selectionRef.current === saving) setStatus(next);
  }

  function cancel() {
    setSelection(null);
    setStatus('idle');
  }

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={[styles.scroll, selection && styles.scrollWithBar]}>
        <View style={styles.column}>
          <Pressable onPress={onBack} hitSlop={12} style={styles.back} accessibilityRole="button">
            <Text style={[styles.backText, { color: palette.muted, fontFamily: fonts.sans }]}>‹ back</Text>
          </Pressable>

          <Text style={[styles.meta, { color: palette.muted, fontFamily: fonts.sans }]}>
            {article.source} · {article.read_minutes} min
          </Text>
          <Text style={[styles.title, { color: palette.ink, fontFamily: fonts.serif }]}>{article.title}</Text>

          {paragraphs.map((tokens, i) => (
            <Paragraph
              key={i}
              index={i}
              tokens={tokens}
              selectedStart={selection?.paragraph === i ? selection.start : null}
              saved={savedHere}
              palette={palette}
              onWordPress={onWordPress}
            />
          ))}
        </View>
      </ScrollView>

      {selection && (
        <View style={styles.barWrap}>
          <View style={[styles.bar, { backgroundColor: palette.surface, borderColor: palette.rule }]}>
            <SelectableWord word={selection.word} palette={palette} />
            {status === 'saved' ? (
              <Text style={[styles.action, { color: palette.muted, fontFamily: fonts.sans }]}>saved</Text>
            ) : alreadySaved ? (
              <Text style={[styles.action, { color: palette.muted, fontFamily: fonts.sans }]}>already saved</Text>
            ) : (
              <Pressable onPress={save} disabled={status === 'saving'} hitSlop={10} accessibilityRole="button">
                <Text style={[styles.action, { color: palette.accent, fontFamily: fonts.sans }]}>
                  {status === 'error' ? 'retry' : 'save'}
                </Text>
              </Pressable>
            )}
            {status !== 'saved' && (
              <Pressable onPress={cancel} hitSlop={10} accessibilityRole="button">
                <Text style={[styles.action, { color: palette.muted, fontFamily: fonts.sans }]}>cancel</Text>
              </Pressable>
            )}
          </View>
        </View>
      )}
    </View>
  );
}

type ParagraphProps = {
  index: number;
  tokens: Token[];
  selectedStart: number | null;
  saved: Set<string>;
  palette: Palette;
  onWordPress: (paragraph: number, token: Token) => void;
};

// memoised so tapping a word only re-renders the paragraph it is in.
const Paragraph = memo(function Paragraph({ index, tokens, selectedStart, saved, palette, onWordPress }: ParagraphProps) {
  return (
    <Text selectable style={[styles.paragraph, { color: palette.ink, fontFamily: fonts.serif }]}>
      {tokens.map((t) => {
        if (!t.isWord) return t.text;
        const isSelected = t.start === selectedStart;
        const isSaved = saved.has(t.text.toLowerCase());
        return (
          <Text
            key={t.start}
            onPress={() => onWordPress(index, t)}
            style={[
              isSelected && { backgroundColor: palette.highlight },
              isSaved && [styles.saved, { textDecorationColor: palette.accent }],
            ]}
          >
            {t.text}
          </Text>
        );
      })}
    </Text>
  );
});

// on ios a read-only multiline text input is a real text view, so long-press on
// the word gives the system menu with look up. a selectable <Text> only offers copy.
function SelectableWord({ word, palette }: { word: string; palette: Palette }) {
  const style = [styles.word, { color: palette.ink, fontFamily: fonts.serif }];
  if (Platform.OS === 'ios') {
    return <TextInput value={word} editable={false} multiline scrollEnabled={false} style={style} />;
  }
  return (
    <Text selectable numberOfLines={1} style={style}>
      {word}
    </Text>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  scroll: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 64 },
  scrollWithBar: { paddingBottom: 140 },
  column: { width: '100%', maxWidth: 640, alignSelf: 'center' },
  back: { alignSelf: 'flex-start', paddingVertical: 8, marginBottom: 32 },
  backText: { fontSize: 16 },
  meta: { fontSize: 12, letterSpacing: 1.4, textTransform: 'uppercase' },
  title: { fontSize: 32, lineHeight: 40, marginTop: 12, marginBottom: 36 },
  paragraph: { fontSize: 19, lineHeight: 30, marginBottom: 22 },
  saved: { textDecorationLine: 'underline', textDecorationStyle: 'dotted' },
  barWrap: { position: 'absolute', left: 0, right: 0, bottom: 16, paddingHorizontal: 16, alignItems: 'center' },
  bar: {
    width: '100%',
    maxWidth: 608,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 24,
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
  },
  word: { flex: 1, fontSize: 19, padding: 0 },
  action: { fontSize: 15, letterSpacing: 0.3 },
});
