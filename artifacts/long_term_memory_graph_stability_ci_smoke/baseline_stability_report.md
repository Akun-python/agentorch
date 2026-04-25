# Long-Term Memory Graph Baseline Stability Benchmark

- Prefix: `benchmark-stability-`
- Seeds: `0, 1, 2`
- Case limit: `3`
- Bootstrap samples: `200`
- Confidence level: `0.95`

## Aggregate Stability

| Baseline | recall mean [95% CI] | relevance mean [95% CI] | relation mean [95% CI] | usefulness mean [95% CI] | stale mean [95% CI] | conflict mean [95% CI] | latency mean [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `no_long_term_memory` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0002 [0.0002, 0.0003]` |
| `vector_memory` | `0.1111 [0.0, 0.25]` | `0.0926 [0.0556, 0.1667]` | `0.0 [0.0, 0.0]` | `0.0871 [0.0445, 0.1667]` | `0.1482 [0.0556, 0.2037]` | `0.3333 [0.0, 0.5556]` | `1.8794 [1.5597, 2.0767]` |
| `flat_summary_memory` | `1.0 [1.0, 1.0]` | `0.8333 [0.8333, 0.8333]` | `0.0 [0.0, 0.0]` | `0.75 [0.75, 0.75]` | `0.0 [0.0, 0.0]` | `1.0 [1.0, 1.0]` | `1.8145 [1.6378, 2.0193]` |
| `naive_graph_memory` | `0.1667 [0.0833, 0.25]` | `0.1111 [0.0556, 0.1667]` | `0.0 [0.0, 0.0]` | `0.1111 [0.0556, 0.1667]` | `0.4815 [0.4444, 0.5]` | `0.6667 [0.3333, 1.0]` | `8.0107 [7.415, 8.3416]` |
| `clarks_nutcracker_graph` | `0.6945 [0.6667, 0.7222]` | `0.5 [0.4444, 0.5371]` | `0.034 [0.0278, 0.0371]` | `0.4935 [0.4389, 0.55]` | `0.0 [0.0, 0.0]` | `1.0 [1.0, 1.0]` | `15.1317 [13.9936, 17.044]` |

## Per Seed

### seed 0
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.0`, relevance `0.0556`, relation `0.0`, usefulness `0.0389`, stale `0.2222`, conflict `0.0`, latency `1.5597` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.6378` ms
- `naive_graph_memory`: recall `0.0833`, relevance `0.0556`, relation `0.0`, usefulness `0.0556`, stale `0.4444`, conflict `0.3333`, latency `7.415` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.5556`, relation `0.0371`, usefulness `0.55`, stale `0.0`, conflict `1.0`, latency `13.6295` ms

### seed 1
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.0833`, relevance `0.0556`, relation `0.0`, usefulness `0.0556`, stale `0.0556`, conflict `0.3333`, latency `1.927` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.0193` ms
- `naive_graph_memory`: recall `0.1667`, relevance `0.1111`, relation `0.0`, usefulness `0.1111`, stale `0.5`, conflict `0.6667`, latency `8.3416` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.4444`, relation `0.0278`, usefulness `0.4389`, stale `0.0`, conflict `1.0`, latency `14.7217` ms

### seed 2
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0003` ms
- `vector_memory`: recall `0.25`, relevance `0.1667`, relation `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `0.6667`, latency `2.1515` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.7863` ms
- `naive_graph_memory`: recall `0.25`, relevance `0.1667`, relation `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `8.2755` ms
- `clarks_nutcracker_graph`: recall `0.75`, relevance `0.5`, relation `0.0371`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `17.044` ms
