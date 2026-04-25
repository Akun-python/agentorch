# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed01-`
- Cases: `3`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0002` |
| `vector_memory` | `0.0833` | `0.0556` | `0.0` | `0.0556` | `0.0556` | `0.3333` | `1.927` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `2.0193` |
| `naive_graph_memory` | `0.1667` | `0.1111` | `0.0` | `0.1111` | `0.5` | `0.6667` | `8.3416` |
| `clarks_nutcracker_graph` | `0.6667` | `0.4444` | `0.0278` | `0.4389` | `0.0` | `1.0` | `14.7217` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0003` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `2.4762` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.4218` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.8831` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.9312` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.4256` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.701` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `8.6124` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.5`, conflict `0.0`, latency `6.8339` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `9.5784` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `15.2133` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `14.4248` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `14.5271` ms
