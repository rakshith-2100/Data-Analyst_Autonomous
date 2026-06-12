The previous code was correct but too expensive — it timed out or ran out of memory. Rewrite
it to use LESS work while answering the SAME question (e.g. df.sample(n=...), chunked
aggregation, fewer intermediate copies).

The environment already has `df`, `pd`, `np`, `plt`. Use ONLY columns from the PROFILE.
`print()` the result; save any chart to `./out/` and print its path.

Output a single ```python code block and nothing else.
