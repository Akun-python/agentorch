# Long-Term Memory Graph Baseline Stability Benchmark

- Prefix: `benchmark-stability-`
- Seeds: `0, 1, 2, 3, 4`
- Case limit: `all`
- Bootstrap samples: `1000`
- Confidence level: `0.95`

## Aggregate Stability

| Baseline | recall mean [95% CI] | relevance mean [95% CI] | relation mean [95% CI] | usefulness mean [95% CI] | stale mean [95% CI] | conflict mean [95% CI] | latency mean [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `no_long_term_memory` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0 [0.0, 0.0]` | `0.0002 [0.0002, 0.0002]` |
| `vector_memory` | `0.1458 [0.1042, 0.1833]` | `0.1111 [0.0944, 0.1278]` | `0.0 [0.0, 0.0]` | `0.1057 [0.09, 0.1214]` | `0.1695 [0.1361, 0.2083]` | `0.4833 [0.3167, 0.65]` | `2.3488 [2.0298, 2.5846]` |
| `flat_summary_memory` | `1.0 [1.0, 1.0]` | `0.8333 [0.8333, 0.8333]` | `0.0 [0.0, 0.0]` | `0.75 [0.75, 0.75]` | `0.0 [0.0, 0.0]` | `1.0 [1.0, 1.0]` | `2.5694 [2.1066, 2.89]` |
| `naive_graph_memory` | `0.325 [0.2875, 0.3583]` | `0.2167 [0.1889, 0.2389]` | `0.0069 [0.0041, 0.0097]` | `0.2164 [0.1917, 0.2383]` | `0.3972 [0.3555, 0.4333]` | `0.9 [0.8167, 0.9667]` | `10.0294 [8.8399, 10.9718]` |
| `clarks_nutcracker_graph` | `0.6417 [0.6167, 0.6708]` | `0.4388 [0.4194, 0.4583]` | `0.0352 [0.031, 0.0399]` | `0.4332 [0.4143, 0.4521]` | `0.0 [0.0, 0.0]` | `0.9833 [0.95, 1.0]` | `19.314 [16.9177, 21.4137]` |

## Per Seed

### seed 0
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.0833`, relevance `0.1111`, relation `0.0`, usefulness `0.0924`, stale `0.2361`, conflict `0.1667`, latency `1.7092` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.7488` ms
- `naive_graph_memory`: recall `0.3542`, relevance `0.2361`, relation `0.0116`, usefulness `0.2347`, stale `0.4167`, conflict `0.9167`, latency `7.7985` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.4722`, relation `0.0347`, usefulness `0.466`, stale `0.0`, conflict `1.0`, latency `15.115` ms

### seed 1
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.1667`, relevance `0.1111`, relation `0.0`, usefulness `0.107`, stale `0.1111`, conflict `0.5`, latency `2.5385` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.6432` ms
- `naive_graph_memory`: recall `0.3125`, relevance `0.2083`, relation `0.0069`, usefulness `0.2083`, stale `0.375`, conflict `0.9167`, latency `10.3036` ms
- `clarks_nutcracker_graph`: recall `0.625`, relevance `0.4166`, relation `0.0324`, usefulness `0.4111`, stale `0.0`, conflict `1.0`, latency `19.4931` ms

### seed 2
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.2083`, relevance `0.1389`, relation `0.0`, usefulness `0.1389`, stale `0.1667`, conflict `0.75`, latency `2.4746` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.887` ms
- `naive_graph_memory`: recall `0.3333`, relevance `0.2222`, relation `0.0069`, usefulness `0.2222`, stale `0.4444`, conflict `1.0`, latency `10.5005` ms
- `clarks_nutcracker_graph`: recall `0.6875`, relevance `0.4583`, relation `0.0278`, usefulness `0.4514`, stale `0.0`, conflict `1.0`, latency `19.8236` ms

### seed 3
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.1042`, relevance `0.0833`, relation `0.0`, usefulness `0.0792`, stale `0.1667`, conflict `0.4167`, latency `2.6579` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.9976` ms
- `naive_graph_memory`: recall `0.375`, relevance `0.25`, relation `0.0069`, usefulness `0.25`, stale `0.3194`, conflict `0.9167`, latency `11.4071` ms
- `clarks_nutcracker_graph`: recall `0.6042`, relevance `0.4305`, relation `0.0371`, usefulness `0.4257`, stale `0.0`, conflict `1.0`, latency `22.7185` ms

### seed 4
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.1667`, relevance `0.1111`, relation `0.0`, usefulness `0.1111`, stale `0.1667`, conflict `0.5833`, latency `2.3636` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.5702` ms
- `naive_graph_memory`: recall `0.25`, relevance `0.1667`, relation `0.0023`, usefulness `0.1667`, stale `0.4305`, conflict `0.75`, latency `10.1371` ms
- `clarks_nutcracker_graph`: recall `0.625`, relevance `0.4166`, relation `0.044`, usefulness `0.4118`, stale `0.0`, conflict `0.9167`, latency `19.42` ms
