// @ts-nocheck -- run by node --test --experimental-strip-types; the app tsconfig has no node types.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cleanWord, sentenceAt, tokenize } from './text.ts';

const words = (p: string) => tokenize(p).filter((t) => t.isWord).map((t) => t.text);

test('tokenize keeps every character', () => {
  const p = '“Well,” she said — it’s a well-known fact (mostly).';
  assert.equal(tokenize(p).map((t) => t.text).join(''), p);
});

test('tokenize offsets point at the token text', () => {
  const p = 'One, two; three.';
  for (const t of tokenize(p)) assert.equal(p.slice(t.start, t.start + t.text.length), t.text);
});

test('tokenize splits off punctuation but keeps inner apostrophes and hyphens', () => {
  assert.deepEqual(words('“Don’t,” said the well-known (author).'), ['Don’t', 'said', 'the', 'well-known', 'author']);
  assert.deepEqual(words("it's rock'n'roll"), ["it's", "rock'n'roll"]);
});

test('tokenize splits on em dashes and treats bare numbers as non-words', () => {
  assert.deepEqual(words('war—peace in 1869'), ['war', 'peace', 'in']);
});

test('tokenize handles accented letters', () => {
  assert.deepEqual(words('a café naïve'), ['a', 'café', 'naïve']);
});

test('cleanWord strips surrounding punctuation only', () => {
  assert.equal(cleanWord('“quixotic,”'), 'quixotic');
  assert.equal(cleanWord('-self-aware.'), 'self-aware');
  assert.equal(cleanWord("'students'"), 'students');
  assert.equal(cleanWord('...'), '');
});

test('sentenceAt returns the sentence containing the offset', () => {
  const p = 'First one here. The second is quixotic! Third? Yes.';
  assert.equal(sentenceAt(p, p.indexOf('quixotic')), 'The second is quixotic!');
  assert.equal(sentenceAt(p, 0), 'First one here.');
  assert.equal(sentenceAt(p, p.indexOf('Yes')), 'Yes.');
});

test('sentenceAt keeps closing quotes with their sentence', () => {
  const p = 'He said, “Stop.” Then he left.';
  assert.equal(sentenceAt(p, p.indexOf('Stop')), 'He said, “Stop.”');
  assert.equal(sentenceAt(p, p.indexOf('left')), 'Then he left.');
});

test('sentenceAt does not split before a lowercase word', () => {
  const p = 'Some fruit, e.g. apples, are sweet. Others are not.';
  assert.equal(sentenceAt(p, p.indexOf('apples')), 'Some fruit, e.g. apples, are sweet.');
});

test('sentenceAt returns the whole paragraph when there is one sentence', () => {
  assert.equal(sentenceAt('  no full stop at all  ', 5), 'no full stop at all');
});

test('sentenceAt does not split after common abbreviations and initials', () => {
  const p = 'Mr. Smith met Dr. Lee. The U.S. President spoke. So did I. Then J. K. Rowling left.';
  assert.equal(sentenceAt(p, p.indexOf('Smith')), 'Mr. Smith met Dr. Lee.');
  assert.equal(sentenceAt(p, p.indexOf('President')), 'The U.S. President spoke.');
  assert.equal(sentenceAt(p, p.indexOf('did')), 'So did I.');
  assert.equal(sentenceAt(p, p.indexOf('Rowling')), 'Then J. K. Rowling left.');
});
