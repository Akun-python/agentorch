# Long-Term Memory Graph Baseline Stability Benchmark

- Prefix: `benchmark-stability-`
- Seeds: `0, 1`
- Case limit: `all`
- Bootstrap samples: `200`
- Confidence level: `0.95`

## Aggregate Stability

| Baseline | recall mean [95% CI] | relevance mean [95% CI] | relation mean [95% CI] | usefulness mean [95% CI] | stale mean [95% CI] | conflict mean [95% CI] | latency mean [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `no_long_term_memory` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0001 [0.0001, 0.0001]` |
| `vector_memory` | `0.125 [0.0833, 0.1667]` | `0.1111 [0.1111, 0.1111]` | `0.0 [0.0, 0.0]` | `0.0997 [0.0924, 0.107]` | `0.1736 [0.1111, 0.2361]` | `0.3333 [0.1667, 0.5]` | `1.1704 [1.149, 1.1917]` |
| `flat_summary_memory` | `1.0 [1.0, 1.0]` | `0.8333 [0.8333, 0.8333]` | `0.0 [0.0, 0.0]` | `0.75 [0.75, 0.75]` | `0.0 [0.0, 0.0]` | `1.0 [1.0, 1.0]` | `1.2601 [1.2547, 1.2655]` |
| `naive_graph_memory` | `0.2188 [0.2083, 0.2292]` | `0.1458 [0.1389, 0.1528]` | `0.0011 [0.0, 0.0023]` | `0.1458 [0.1389, 0.1528]` | `0.4166 [0.4028, 0.4305]` | `0.75 [0.75, 0.75]` | `5.3105 [5.187, 5.4339]` |
| `clarks_nutcracker_graph` | `0.6459 [0.625, 0.6667]` | `0.4444 [0.4166, 0.4722]` | `0.0335 [0.0324, 0.0347]` | `0.4385 [0.4111, 0.466]` | `0.0 [0.0, 0.0]` | `1.0 [1.0, 1.0]` | `10.1949 [9.9548, 10.435]` |

## Per Seed

### seed 0
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vector_memory`: recall `0.0833`, relevance `0.1111`, relation `0.0`, usefulness `0.0924`, stale `0.2361`, conflict `0.1667`, latency `1.1917` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2655` ms
- `naive_graph_memory`: recall `0.2083`, relevance `0.1389`, relation `0.0023`, usefulness `0.1389`, stale `0.4305`, conflict `0.75`, latency `5.4339` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.4722`, relation `0.0347`, usefulness `0.466`, stale `0.0`, conflict `1.0`, latency `10.435` ms

### seed 1
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vector_memory`: recall `0.1667`, relevance `0.1111`, relation `0.0`, usefulness `0.107`, stale `0.1111`, conflict `0.5`, latency `1.149` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2547` ms
- `naive_graph_memory`: recall `0.2292`, relevance `0.1528`, relation `0.0`, usefulness `0.1528`, stale `0.4028`, conflict `0.75`, latency `5.187` ms
- `clarks_nutcracker_graph`: recall `0.625`, relevance `0.4166`, relation `0.0324`, usefulness `0.4111`, stale `0.0`, conflict `1.0`, latency `9.9548` ms
