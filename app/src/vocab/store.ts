// saved words, persisted in async storage. one module-level cache so every
// useVocab() caller sees the same list and re-renders together.
import { useSyncExternalStore } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { VocabWord } from '../types';
import { isDue, localToday, newWord, review as reviewWord, type NewWordInput } from '../lib/leitner';

const KEY = 'vocab.v1';
const BACKUP_KEY = 'vocab.v1.corrupt';

let words: VocabWord[] = [];
let loading: Promise<void> | null = null;
const listeners = new Set<() => void>();

// if loading fails, nothing may be written: an empty list would overwrite the
// saved words on disk. a failed read is retried on the next call.
function load(): Promise<void> {
  if (!loading) {
    loading = AsyncStorage.getItem(KEY)
      .then(async (raw) => {
        if (!raw) return;
        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch {
          parsed = null;
        }
        if (!Array.isArray(parsed)) {
          // keep the unreadable data before the next save replaces it.
          await AsyncStorage.setItem(BACKUP_KEY, raw);
          console.warn('vocab: saved words were unreadable, copied to ' + BACKUP_KEY);
          return;
        }
        set(parsed.filter((w) => typeof w?.word === 'string' && typeof w?.id === 'string'));
      })
      .catch((e) => {
        loading = null;
        throw e;
      });
  }
  return loading;
}

function set(next: VocabWord[]): void {
  words = next;
  listeners.forEach((l) => l());
}

// throws if loading or writing fails; on a failed write the list rolls back.
async function commit(update: (current: VocabWord[]) => VocabWord[]): Promise<void> {
  await load();
  const previous = words;
  const next = update(previous);
  set(next);
  try {
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
  } catch (e) {
    if (words === next) set(previous);
    throw e;
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  load().catch((e) => console.warn('vocab: could not load saved words', e));
  return () => listeners.delete(listener);
}

function getSnapshot(): VocabWord[] {
  return words;
}

async function saveWord(input: NewWordInput): Promise<void> {
  const key = input.word.trim().toLowerCase();
  if (!key) return;
  await commit((current) =>
    current.some((w) => w.word.toLowerCase() === key) ? current : [...current, newWord(input)],
  );
}

async function review(id: string, correct: boolean): Promise<void> {
  const today = localToday();
  await commit((current) => current.map((w) => (w.id === id ? reviewWord(w, correct, today) : w)));
}

async function remove(id: string): Promise<void> {
  await commit((current) => current.filter((w) => w.id !== id));
}

function exportJson(): string {
  return JSON.stringify(words, null, 2);
}

export function useVocab() {
  const all = useSyncExternalStore(subscribe, getSnapshot);
  const today = localToday();
  const dueWords = all.filter((w) => isDue(w, today));
  return { words: all, dueWords, dueCount: dueWords.length, saveWord, review, remove, exportJson };
}
