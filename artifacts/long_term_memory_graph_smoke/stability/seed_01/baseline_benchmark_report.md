# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed01-`
- Cases: `12`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0001` |
| `vector_memory` | `0.1667` | `0.1111` | `0.0` | `0.107` | `0.1111` | `0.5` | `1.149` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `1.2547` |
| `naive_graph_memory` | `0.2292` | `0.1528` | `0.0` | `0.1528` | `0.4028` | `0.75` | `5.187` |
| `clarks_nutcracker_graph` | `0.625` | `0.4166` | `0.0324` | `0.4111` | `0.0` | `1.0` | `9.9548` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0003` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_zephyr_invoice`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.0879` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.3108` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.1293` ms
- `vendor_orion_procurement`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3083`, stale `0.3333`, conflict `1.0`, latency `1.1838` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.1056` ms
- `customer_titan_support`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.1936` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.1009` ms
- `demand_forecast_analytics`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3083`, stale `0.3333`, conflict `1.0`, latency `1.1063` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.1473` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.1622` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.1309` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.1299` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.1336` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2737` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3612` ms
- `vendor_orion_procurement`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3599` ms
- `vendor_zephyr_invoice`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2118` ms
- `customer_titan_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.4066` ms
- `customer_nova_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2347` ms
- `demand_forecast_analytics`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.187` ms
- `nutcracker_memory_research`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2185` ms
- `elephant_context_runtime`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2936` ms
- `compliance_audit_eu`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.1986` ms
- `warehouse_robot_ops`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.1772` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.6667`, conflict `0.0`, latency `5.488` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `5.039` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `4.8798` ms
- `vendor_orion_procurement`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.2884` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `4.8547` ms
- `customer_titan_support`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.2893` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.5`, conflict `0.0`, latency `5.3356` ms
- `demand_forecast_analytics`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `5.3791` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.3333`, conflict `0.0`, latency `5.1042` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `5.5731` ms
- `compliance_audit_eu`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `4.9542` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `5.0589` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `10.5992` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.8938` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.4048` ms
- `vendor_orion_procurement`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.9131` ms
- `vendor_zephyr_invoice`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.7076` ms
- `customer_titan_support`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.9811` ms
- `customer_nova_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.325`, stale `0.0`, conflict `1.0`, latency `10.0457` ms
- `demand_forecast_analytics`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.822` ms
- `nutcracker_memory_research`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `9.6931` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.325`, stale `0.0`, conflict `1.0`, latency `10.4514` ms
- `compliance_audit_eu`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.1111`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `9.8342` ms
- `warehouse_robot_ops`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `10.1111` ms
