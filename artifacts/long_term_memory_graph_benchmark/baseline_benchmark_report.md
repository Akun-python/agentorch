# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-`
- Cases: `12`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0002` |
| `vector_memory` | `0.1042` | `0.0694` | `0.0` | `0.0681` | `0.1389` | `0.25` | `1.5491` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `1.6444` |
| `naive_graph_memory` | `0.3125` | `0.2083` | `0.0069` | `0.2077` | `0.4167` | `0.8333` | `6.839` |
| `clarks_nutcracker_graph` | `0.6458` | `0.4305` | `0.0324` | `0.4243` | `0.0` | `1.0` | `13.4797` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0005` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0003` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_zephyr_invoice`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.7316` ms
- `deploy_beta_staging`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.325`, stale `0.3333`, conflict `1.0`, latency `1.2784` ms
- `api_gateway_patch`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.325`, stale `0.3333`, conflict `1.0`, latency `1.7748` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2884` ms
- `vendor_zephyr_invoice`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.3998` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.3182` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.9094` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.4202` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `2.1693` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.3356` ms
- `compliance_audit_eu`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `1.3346` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.6284` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.9176` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2867` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.5197` ms
- `vendor_orion_procurement`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.316` ms
- `vendor_zephyr_invoice`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.7895` ms
- `customer_titan_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.7647` ms
- `customer_nova_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.6858` ms
- `demand_forecast_analytics`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.5588` ms
- `nutcracker_memory_research`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.6659` ms
- `elephant_context_runtime`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.559` ms
- `compliance_audit_eu`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.4363` ms
- `warehouse_robot_ops`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.2332` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.6667`, conflict `0.0`, latency `7.6366` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.8537` ms
- `api_gateway_patch`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.1662` ms
- `vendor_orion_procurement`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `5.1977` ms
- `vendor_zephyr_invoice`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `8.1199` ms
- `customer_titan_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `6.2003` ms
- `customer_nova_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `7.4014` ms
- `demand_forecast_analytics`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `7.6202` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.5`, conflict `0.0`, latency `7.6378` ms
- `elephant_context_runtime`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `6.9991` ms
- `compliance_audit_eu`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `7.3387` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.6667`, conflict `1.0`, latency `6.8966` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `14.3331` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `11.3205` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.5545` ms
- `vendor_orion_procurement`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `13.4111` ms
- `vendor_zephyr_invoice`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `12.8843` ms
- `customer_titan_support`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `12.5602` ms
- `customer_nova_support`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `13.9696` ms
- `demand_forecast_analytics`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `14.3238` ms
- `nutcracker_memory_research`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `14.1601` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.325`, stale `0.0`, conflict `1.0`, latency `17.7255` ms
- `compliance_audit_eu`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `13.9775` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.0`, conflict `1.0`, latency `12.5363` ms
