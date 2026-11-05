// shared contract between the samples export, the reader and the vocab store.

export type Article = {
  id: string; // url hash from the python fetcher
  title: string;
  source: string;
  bucket: string;
  url: string;
  read_minutes: number;
  published_at: string | null;
  paragraphs: string[];
};

export type SampleFile = {
  generated_at: string;
  articles: Article[];
};

export type VocabWord = {
  id: string;
  word: string;
  sentence: string; // the sentence the word was saved from
  articleId: string;
  articleTitle: string;
  source: string;
  box: 1 | 2 | 3 | 4 | 5; // leitner box
  due: string; // YYYY-MM-DD, local date
  addedAt: string; // ISO timestamp
};
