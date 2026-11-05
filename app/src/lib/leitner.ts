// leitner spaced review. pure logic, no react native imports.
// dates are local calendar days as 'YYYY-MM-DD' strings.
import type { VocabWord } from '../types';

type Box = VocabWord['box'];

export const INTERVALS: Record<Box, number> = { 1: 1, 2: 2, 3: 4, 4: 8, 5: 16 };

export type NewWordInput = {
  word: string;
  sentence: string;
  articleId: string;
  articleTitle: string;
  source: string;
};

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

// local calendar date of a moment, e.g. '2026-11-05'.
export function toLocalDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function localToday(): string {
  return toLocalDate(new Date());
}

// calendar-day arithmetic done in utc so dst shifts never skip or repeat a day.
export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`;
}

export function newWord(input: NewWordInput, now: Date = new Date()): VocabWord {
  const addedAt = now.toISOString();
  const word = input.word.trim();
  return {
    id: `${word.toLowerCase()}-${addedAt}`,
    word,
    sentence: input.sentence,
    articleId: input.articleId,
    articleTitle: input.articleTitle,
    source: input.source,
    box: 1,
    due: toLocalDate(now), // reviewable the same day
    addedAt,
  };
}

export function review(word: VocabWord, correct: boolean, today: string): VocabWord {
  if (!correct) return { ...word, box: 1, due: addDays(today, 1) };
  const box = Math.min(word.box + 1, 5) as Box;
  return { ...word, box, due: addDays(today, INTERVALS[box]) };
}

export function isDue(word: VocabWord, today: string): boolean {
  return word.due <= today; // YYYY-MM-DD sorts lexically
}
