import { expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ResearchView } from './ResearchView';

it('marks the read-only research section as simulated with no broker order', () => {
  const html = renderToStaticMarkup(<ResearchView />);
  expect(html).toContain('RESEARCH ONLY');
  expect(html).toContain('SIMULATED');
  expect(html).toContain('NO BROKER ORDER');
  expect(html).toContain('Accepted LONG snapshots saved before this checkpoint');
  expect(html).toContain('Operator evaluation history');
  expect(html).toContain('this page cannot create orders');
});
