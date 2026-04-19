# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed00-`
- Cases: `3`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0002` |
| `vector_memory` | `0.0` | `0.0556` | `0.0` | `0.0389` | `0.2222` | `0.0` | `1.2951` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `1.3461` |
| `naive_graph_memory` | `0.25` | `0.1667` | `0.0093` | `0.1667` | `0.4444` | `0.6667` | `5.778` |
| `clarks_nutcracker_graph` | `0.6667` | `0.5556` | `0.0371` | `0.55` | `0.0` | `1.0` | `11.7086` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0005` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1167`, stale `0.3333`, conflict `0.0`, latency `1.3309` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2501` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.3044` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.387` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2963` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3549` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.6667`, conflict `0.0`, latency `5.4723` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `5.8563` ms
- `api_gateway_patch`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `6.0055` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.6667`, relation_hit `0.0556`, usefulness `0.6667`, stale `0.0`, conflict `1.0`, latency `12.3978` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `11.2359` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `11.492` ms
