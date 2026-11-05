// saved words: a quiet list, and a one-card-at-a-time leitner review.
import { useState } from 'react';
import { Pressable, ScrollView, Share, StyleSheet, Text, View } from 'react-native';
import { fonts, usePalette, type Palette } from '../theme';
import type { VocabWord } from '../types';
import { tokenize } from '../lib/text';
import { useVocab } from './store';

type Props = { onBack: () => void };

export default function VocabScreen({ onBack }: Props) {
  const p = usePalette();
  const { words, dueWords, dueCount, review, remove, exportJson } = useVocab();
  // ids due when the session started; reviewed words drop out of dueWords but stay in the queue.
  const [queue, setQueue] = useState<string[] | null>(null);
  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState(false);
  // remove asks once ('remove?') before deleting a word and its progress.
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  const reviewing = queue !== null;
  const current = reviewing ? words.find((w) => w.id === queue[index]) : undefined;

  function startReview() {
    setQueue(dueWords.map((w) => w.id));
    setIndex(0);
    setShown(false);
  }

  function stopReview() {
    setQueue(null);
  }

  async function answer(correct: boolean) {
    if (!current) return;
    // advance first so a quick double tap can't grade the same card twice.
    setShown(false);
    setIndex((i) => i + 1);
    await review(current.id, correct).catch((e) => console.warn('vocab: could not save review', e));
  }

  function onRemove(id: string) {
    if (confirmRemove !== id) {
      setConfirmRemove(id);
      return;
    }
    setConfirmRemove(null);
    remove(id).catch((e) => console.warn('vocab: could not remove word', e));
  }

  function onExport() {
    Share.share({ message: exportJson() }).catch((e) => console.warn('vocab: could not share', e));
  }

  const newest = [...words].sort((a, b) => b.addedAt.localeCompare(a.addedAt));

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: p.bg }}
      contentContainerStyle={styles.page}
    >
      <View style={styles.header}>
        <TextButton label={reviewing ? '‹ words' : '‹ back'} onPress={reviewing ? stopReview : onBack} p={p} />
        {!reviewing && words.length > 0 && (
          <TextButton label="export" onPress={onExport} p={p} />
        )}
      </View>

      {reviewing ? (
        current ? (
          <View style={styles.card}>
            <Text style={[styles.counter, { color: p.muted }]}>
              {index + 1} of {queue.length}
            </Text>
            <Text style={[styles.cardWord, { color: p.ink }]}>{current.word}</Text>
            {shown ? (
              <>
                <Sentence word={current.word} sentence={current.sentence} p={p} size={20} />
                <Text style={[styles.meta, { color: p.muted }]}>
                  {current.source} · {current.articleTitle}
                </Text>
                <View style={styles.answers}>
                  <QuietButton label="again" onPress={() => answer(false)} p={p} />
                  <QuietButton label="got it" onPress={() => answer(true)} p={p} />
                </View>
              </>
            ) : (
              <View style={styles.answers}>
                <QuietButton label="show" onPress={() => setShown(true)} p={p} />
              </View>
            )}
          </View>
        ) : (
          <View style={styles.card}>
            <Text style={[styles.done, { color: p.ink }]}>all done for today</Text>
            <View style={styles.answers}>
              <QuietButton label="back to words" onPress={stopReview} p={p} />
            </View>
          </View>
        )
      ) : (
        <>
          <Text style={[styles.title, { color: p.ink }]}>words</Text>

          {dueCount > 0 && (
            <Pressable onPress={startReview} style={[styles.reviewEntry, { borderColor: p.rule }]}>
              <Text style={[styles.reviewText, { color: p.accent }]}>review · {dueCount}</Text>
            </Pressable>
          )}

          {newest.length === 0 ? (
            <Text style={[styles.empty, { color: p.muted }]}>tap any word while reading to save it.</Text>
          ) : (
            newest.map((w) => (
              <View key={w.id} style={[styles.item, { borderBottomColor: p.rule }]}>
                <View style={styles.itemTop}>
                  <Text style={[styles.itemWord, { color: p.ink }]}>{w.word}</Text>
                  <BoxDots box={w.box} p={p} />
                </View>
                <Sentence word={w.word} sentence={w.sentence} p={p} size={16} muted />
                <View style={styles.itemBottom}>
                  <Text style={[styles.itemSource, { color: p.muted }]} numberOfLines={1}>
                    {w.source}
                  </Text>
                  <TextButton label={confirmRemove === w.id ? 'remove?' : 'remove'} onPress={() => onRemove(w.id)} p={p} />
                </View>
              </View>
            ))
          )}
        </>
      )}
    </ScrollView>
  );
}

// the sentence with the saved word set in italic ink.
function Sentence({
  word,
  sentence,
  p,
  size,
  muted = false,
}: {
  word: string;
  sentence: string;
  p: Palette;
  size: number;
  muted?: boolean;
}) {
  const key = word.toLowerCase();
  return (
    <Text
      selectable
      style={{ fontFamily: fonts.serif, fontSize: size, lineHeight: size * 1.55, color: muted ? p.muted : p.ink }}
    >
      {tokenize(sentence).map((t) =>
        t.isWord && t.text.toLowerCase() === key ? (
          <Text key={t.start} style={{ fontStyle: 'italic', color: p.ink }}>
            {t.text}
          </Text>
        ) : (
          t.text
        ),
      )}
    </Text>
  );
}

function BoxDots({ box, p }: { box: VocabWord['box']; p: Palette }) {
  return (
    <View style={styles.dots} accessibilityLabel={`box ${box} of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <View key={n} style={[styles.dot, { backgroundColor: n <= box ? p.muted : p.rule }]} />
      ))}
    </View>
  );
}

function TextButton({ label, onPress, p }: { label: string; onPress: () => void; p: Palette }) {
  return (
    <Pressable onPress={onPress} hitSlop={12}>
      {({ pressed }) => (
        <Text style={[styles.textButton, { color: p.muted, opacity: pressed ? 0.5 : 1 }]}>{label}</Text>
      )}
    </Pressable>
  );
}

function QuietButton({ label, onPress, p }: { label: string; onPress: () => void; p: Palette }) {
  return (
    <Pressable onPress={onPress} hitSlop={8}>
      {({ pressed }) => (
        <View style={[styles.quiet, { borderColor: p.rule, backgroundColor: pressed ? p.surface : 'transparent' }]}>
          <Text style={[styles.quietText, { color: p.ink }]}>{label}</Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  page: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 96, flexGrow: 1 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 40 },
  textButton: { fontFamily: fonts.sans, fontSize: 15, letterSpacing: 0.3 },
  title: { fontFamily: fonts.serif, fontSize: 34, marginBottom: 28 },
  reviewEntry: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 2, paddingVertical: 18, alignItems: 'center', marginBottom: 36 },
  reviewText: { fontFamily: fonts.serif, fontSize: 18, letterSpacing: 0.5 },
  empty: { fontFamily: fonts.serif, fontSize: 17, lineHeight: 27, fontStyle: 'italic', marginTop: 24 },
  item: { paddingVertical: 22, borderBottomWidth: StyleSheet.hairlineWidth, gap: 10 },
  itemTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  itemWord: { fontFamily: fonts.serif, fontSize: 22 },
  itemBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 16 },
  itemSource: { fontFamily: fonts.sans, fontSize: 13, flexShrink: 1 },
  dots: { flexDirection: 'row', gap: 4 },
  dot: { width: 5, height: 5, borderRadius: 2.5 },
  card: { paddingTop: 96, gap: 24 },
  counter: { fontFamily: fonts.sans, fontSize: 13, letterSpacing: 0.5 },
  cardWord: { fontFamily: fonts.serif, fontSize: 44, lineHeight: 54 },
  meta: { fontFamily: fonts.sans, fontSize: 13, lineHeight: 19 },
  answers: { flexDirection: 'row', gap: 16, marginTop: 16 },
  quiet: { borderWidth: StyleSheet.hairlineWidth, borderRadius: 2, paddingVertical: 12, paddingHorizontal: 24 },
  quietText: { fontFamily: fonts.serif, fontSize: 17 },
  done: { fontFamily: fonts.serif, fontSize: 26, fontStyle: 'italic' },
});
