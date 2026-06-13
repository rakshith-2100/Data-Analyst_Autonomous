// Data-aware starter questions + a small id helper.
// Suggestions are derived from the loaded profile so they fit ANY dataset,
// not just the Telco churn sample.
import type { Profile } from './types'

let idCounter = 0
export const nextId = (prefix = 'id') => `${prefix}-${++idCounter}`

const isNumeric = (dtype: string) => /int|float|number/i.test(dtype)
const looksLikeId = (name: string) => /(^|_)id$|^id$|uuid|code$/i.test(name)

// Pick a low-cardinality categorical column and a numeric column, then phrase
// a handful of generic-but-specific prompts around them.
export function suggestQuestions(profile: Profile): string[] {
  const cols = profile.columns
  const categorical = cols.find(
    (c) => !isNumeric(c.dtype) && c.nUnique >= 2 && c.nUnique <= 15 && !looksLikeId(c.name),
  )
  const numeric = cols.find((c) => isNumeric(c.dtype) && c.nUnique > 5 && !looksLikeId(c.name))
  const flagged = cols.find((c) => c.issue)

  const out: string[] = ['Summarise this dataset — what are the columns and what stands out?']

  if (numeric && categorical) {
    out.push(`Average ${numeric.name} by ${categorical.name} as a bar chart.`)
  } else if (numeric) {
    out.push(`What is the average ${numeric.name}?`)
  }

  if (categorical) {
    out.push(`Show the breakdown of ${categorical.name} as a table.`)
  }

  if (flagged) {
    out.push(`What is the average ${flagged.name}?`)
  } else if (numeric) {
    out.push(`Show the distribution of ${numeric.name}.`)
  }

  return out.slice(0, 4)
}
