# Long-Term Memory Graph Baseline Stability Benchmark

- Prefix: `benchmark-stability-`
- Seeds: `0, 1, 2`
- Case limit: `3`

## Aggregate Stability

| Baseline | recall mean +- std | relevance mean +- std | relation mean +- std | usefulness mean +- std | stale mean +- std | conflict mean +- std | latency mean +- std |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `no_long_term_memory` | `0.0 +- 0.0` | `0.0 +- 0.0` | `0.0 +- 0.0` | `0.0 +- 0.0` | `0.0 +- 0.0` | `0.0 +- 0.0` | `0.0002 +- 0.0` |
| `vector_memory` | `0.1111 +- 0.1039` | `0.0926 +- 0.0524` | `0.0 +- 0.0` | `0.0871 +- 0.0567` | `0.1482 +- 0.0693` | `0.3333 +- 0.2722` | `1.7706 +- 0.5341` |
| `flat_summary_memory` | `1.0 +- 0.0` | `0.8333 +- 0.0` | `0.0 +- 0.0` | `0.75 +- 0.0` | `0.0 +- 0.0` | `1.0 +- 0.0` | `1.6638 +- 0.37` |
| `naive_graph_memory` | `0.2222 +- 0.0393` | `0.1482 +- 0.0262` | `0.0031 +- 0.0044` | `0.1482 +- 0.0262` | `0.5 +- 0.0454` | `0.7778 +- 0.1571` | `6.961 +- 1.0639` |
| `clarks_nutcracker_graph` | `0.6945 +- 0.0393` | `0.5 +- 0.0454` | `0.034 +- 0.0044` | `0.4935 +- 0.0454` | `0.0 +- 0.0` | `1.0 +- 0.0` | `14.6448 +- 2.9987` |

## Per Seed

### seed 0
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.0`, relevance `0.0556`, relation `0.0`, usefulness `0.0389`, stale `0.2222`, conflict `0.0`, latency `1.2951` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3461` ms
- `naive_graph_memory`: recall `0.25`, relevance `0.1667`, relation `0.0093`, usefulness `0.1667`, stale `0.4444`, conflict `0.6667`, latency `5.778` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.5556`, relation `0.0371`, usefulness `0.55`, stale `0.0`, conflict `1.0`, latency `11.7086` ms

### seed 1
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `vector_memory`: recall `0.0833`, relevance `0.0556`, relation `0.0`, usefulness `0.0556`, stale `0.0556`, conflict `0.3333`, latency `1.5002` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.4626` ms
- `naive_graph_memory`: recall `0.1667`, relevance `0.1111`, relation `0.0`, usefulness `0.1111`, stale `0.5`, conflict `0.6667`, latency `6.7473` ms
- `clarks_nutcracker_graph`: recall `0.6667`, relevance `0.4444`, relation `0.0278`, usefulness `0.4389`, stale `0.0`, conflict `1.0`, latency `13.4628` ms

### seed 2
- `no_long_term_memory`: recall `0.0`, relevance `0.0`, relation `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0003` ms
- `vector_memory`: recall `0.25`, relevance `0.1667`, relation `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `0.6667`, latency `2.5166` ms
- `flat_summary_memory`: recall `1.0`, relevance `0.8333`, relation `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.1828` ms
- `naive_graph_memory`: recall `0.25`, relevance `0.1667`, relation `0.0`, usefulness `0.1667`, stale `0.5556`, conflict `1.0`, latency `8.3577` ms
- `clarks_nutcracker_graph`: recall `0.75`, relevance `0.5`, relation `0.0371`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `18.7629` ms
