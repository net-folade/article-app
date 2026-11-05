// @ts-nocheck -- run by node --test --experimental-strip-types; the app tsconfig has no node types.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { VocabWord } from '../types';
import { addDays, INTERVALS, isDue, newWord, review, toLocalDate } from './leitner.ts';

const input = {
  word: ' Quixotic ',
  sentence: 'It was a quixotic plan.',
  articleId: 'a1',
  articleTitle: 'On plans',
  source: 'aeon',
};

function at(box: VocabWord['box'], due = '2026-11-05'): VocabWord {
  return { ...newWord(input, new Date(2026, 10, 5, 9, 0)), box, due };
}

test('addDays handles month and year ends', () => {
  assert.equal(addDays('2026-11-05', 1), '2026-11-06');
  assert.equal(addDays('2026-01-31', 1), '2026-02-01');
  assert.equal(addDays('2026-12-31', 1), '2027-01-01');
  assert.equal(addDays('2026-12-20', 16), '2027-01-05');
  assert.equal(addDays('2026-03-01', -1), '2026-02-28');
  assert.equal(addDays('2028-02-28', 1), '2028-02-29');
  assert.equal(addDays('2026-11-05', 0), '2026-11-05');
});

test('addDays is dst safe across spring and autumn changes', () => {
  // us and eu dst transitions in 2026
  assert.equal(addDays('2026-03-07', 1), '2026-03-08');
  assert.equal(addDays('2026-03-08', 1), '2026-03-09');
  assert.equal(addDays('2026-03-28', 2), '2026-03-30');
  assert.equal(addDays('2026-10-24', 2), '2026-10-26');
  assert.equal(addDays('2026-10-31', 1), '2026-11-01');
  assert.equal(addDays('2026-11-01', 1), '2026-11-02');
  // walk a whole year one day at a time: 365 distinct, consecutive days
  let d = '2026-01-01';
  const seen = new Set<string>();
  for (let i = 0; i < 365; i++) {
    seen.add(d);
    d = addDays(d, 1);
  }
  assert.equal(seen.size, 365);
  assert.equal(d, '2027-01-01');
});

test('toLocalDate uses local calendar fields', () => {
  assert.equal(toLocalDate(new Date(2026, 10, 5, 0, 0)), '2026-11-05');
  assert.equal(toLocalDate(new Date(2026, 10, 5, 23, 59)), '2026-11-05');
  assert.equal(toLocalDate(new Date(2026, 0, 9)), '2026-01-09');
});

test('newWord starts in box 1, due today, trimmed, with a stable id', () => {
  const now = new Date(2026, 10, 5, 21, 30);
  const w = newWord(input, now);
  assert.equal(w.box, 1);
  assert.equal(w.due, '2026-11-05');
  assert.equal(w.word, 'Quixotic');
  assert.equal(w.addedAt, now.toISOString());
  assert.equal(w.id, `quixotic-${now.toISOString()}`);
  assert.equal(w.sentence, input.sentence);
  assert.equal(w.articleId, 'a1');
  assert.equal(w.articleTitle, 'On plans');
  assert.equal(w.source, 'aeon');
  assert.ok(isDue(w, '2026-11-05'));
});

test('intervals are 1, 2, 4, 8, 16 days', () => {
  assert.deepEqual(INTERVALS, { 1: 1, 2: 2, 3: 4, 4: 8, 5: 16 });
});

test('correct answers climb a box and schedule by the new box interval', () => {
  const today = '2026-11-05';
  assert.deepEqual(
    [1, 2, 3, 4].map((b) => {
      const r = review(at(b as VocabWord['box']), true, today);
      return [r.box, r.due];
    }),
    [
      [2, '2026-11-07'],
      [3, '2026-11-09'],
      [4, '2026-11-13'],
      [5, '2026-11-21'],
    ],
  );
});

test('box 5 caps at 5', () => {
  const r = review(at(5), true, '2026-11-05');
  assert.equal(r.box, 5);
  assert.equal(r.due, '2026-11-21');
});

test('a wrong answer drops to box 1, due tomorrow', () => {
  for (const b of [1, 2, 3, 4, 5] as const) {
    const r = review(at(b), false, '2026-12-31');
    assert.equal(r.box, 1);
    assert.equal(r.due, '2027-01-01');
  }
});

test('review is pure and keeps the other fields', () => {
  const w = at(2);
  const r = review(w, true, '2026-11-05');
  assert.equal(w.box, 2);
  assert.equal(w.due, '2026-11-05');
  assert.equal(r.id, w.id);
  assert.equal(r.sentence, w.sentence);
  assert.equal(r.addedAt, w.addedAt);
});

test('schedules from the review day, not the old due date', () => {
  const overdue = at(1, '2026-10-01');
  assert.equal(review(overdue, true, '2026-11-05').due, '2026-11-07');
});

test('isDue: due today or earlier', () => {
  assert.ok(isDue(at(1, '2026-11-05'), '2026-11-05'));
  assert.ok(isDue(at(1, '2026-10-30'), '2026-11-05'));
  assert.ok(!isDue(at(1, '2026-11-06'), '2026-11-05'));
  assert.ok(isDue(at(1, '2026-12-31'), '2027-01-01'));
});

test('a full climb from new to box 5', () => {
  let w = newWord(input, new Date(2026, 10, 5, 8));
  let day = w.due;
  const dues: string[] = [];
  for (let i = 0; i < 5; i++) {
    w = review(w, true, day);
    day = w.due;
    dues.push(day);
  }
  assert.deepEqual(dues, ['2026-11-07', '2026-11-11', '2026-11-19', '2026-12-05', '2026-12-21']);
  assert.equal(w.box, 5);
});
