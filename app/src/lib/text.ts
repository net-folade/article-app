// splitting article paragraphs into tappable words. pure logic, no react native imports.

export type Token = {
  text: string;
  start: number; // offset in the paragraph
  isWord: boolean;
};

// letters/digits, with apostrophes or hyphens allowed only between them.
const WORD = /[\p{L}\p{M}\p{N}]+(?:['’-][\p{L}\p{M}\p{N}]+)*/gu;
const HAS_LETTER = /\p{L}/u;

// every character of the paragraph lands in exactly one token, so joining
// the token texts gives the paragraph back unchanged.
export function tokenize(paragraph: string): Token[] {
  const tokens: Token[] = [];
  let last = 0;
  for (const match of paragraph.matchAll(WORD)) {
    const start = match.index ?? 0;
    if (start > last) tokens.push({ text: paragraph.slice(last, start), start: last, isWord: false });
    tokens.push({ text: match[0], start, isWord: HAS_LETTER.test(match[0]) });
    last = start + match[0].length;
  }
  if (last < paragraph.length) tokens.push({ text: paragraph.slice(last), start: last, isWord: false });
  return tokens;
}

// strip surrounding punctuation, keeping apostrophes and hyphens inside the word.
export function cleanWord(raw: string): string {
  const match = raw.match(WORD);
  return match ? match[0] : '';
}

// a sentence ends at . ! ? (plus closing quotes/brackets) followed by space and
// a character that is not lowercase, so 'e.g. this' does not split.
const SENTENCE_END = /[.!?…]+["'”’)\]]*\s+(?=[^\p{Ll}])/gu;

// a full stop after these does not end a sentence: 'Mr. Smith', 'U.S. President', 'J. Smith'.
const ABBREVIATIONS = new Set(['mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'jr', 'sr', 'vs']);
const INITIALS = /^(?:\p{L}\.)*\p{Lu}$/u;

function isAbbreviation(before: string): boolean {
  const word = before.match(/[\p{L}.]+$/u)?.[0] ?? '';
  return ABBREVIATIONS.has(word.toLowerCase()) || (word !== 'I' && INITIALS.test(word));
}

// the full sentence of the paragraph that contains the character at offset.
export function sentenceAt(paragraph: string, offset: number): string {
  let start = 0;
  let end = paragraph.length;
  for (const match of paragraph.matchAll(SENTENCE_END)) {
    const index = match.index ?? 0;
    if (match[0].startsWith('. ') && isAbbreviation(paragraph.slice(0, index))) continue;
    const boundary = index + match[0].length;
    if (boundary <= offset) {
      start = boundary;
    } else {
      end = boundary;
      break;
    }
  }
  return paragraph.slice(start, end).trim();
}
