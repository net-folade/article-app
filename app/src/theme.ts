// calm reader palette. light is warm paper, dark is warm ink.
import { useColorScheme } from 'react-native';

const light = {
  bg: '#FAF7F0',
  surface: '#F2EDE3',
  ink: '#1E1C19',
  muted: '#8A8378',
  rule: '#E3DCCF',
  accent: '#9A5B34',
  highlight: '#F1DFC6',
};

const dark = {
  bg: '#141311',
  surface: '#1E1C19',
  ink: '#ECE6DA',
  muted: '#8F887C',
  rule: '#2B2824',
  accent: '#D4A27A',
  highlight: '#3A2E22',
};

export type Palette = typeof light;

export const fonts = {
  serif: 'Georgia',
  sans: undefined as string | undefined, // system font
};

export function usePalette(): Palette {
  return useColorScheme() === 'dark' ? dark : light;
}
