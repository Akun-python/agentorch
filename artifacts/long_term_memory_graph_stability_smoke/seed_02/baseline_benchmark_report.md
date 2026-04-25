# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed02-`
- Cases: `3`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0003` |
| `vector_memory` | `0.25` | `0.1667` | `0.0` | `0.1667` | `0.1667` | `0.6667` | `2.5166` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `2.1828` |
| `naive_graph_memory` | `0.25` | `0.1667` | `0.0` | `0.1667` | `0.5556` | `1.0` | `8.3577` |
| `clarks_nutcracker_graph` | `0.75` | `0.5` | `0.0371` | `0.4917` | `0.0` | `1.0` | `18.7629` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0004` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `2.0382` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `2.2493` ms
- `api_gateway_patch`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `3.2622` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.9711` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.9859` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.5913` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.6667`, conflict `1.0`, latency `8.3216` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `8.3382` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `8.4132` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `19.0278` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `17.9942` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `19.2667` ms
