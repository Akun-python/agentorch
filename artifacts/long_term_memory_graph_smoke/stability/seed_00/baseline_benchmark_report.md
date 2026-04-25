# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed00-`
- Cases: `12`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0001` |
| `vector_memory` | `0.0833` | `0.1111` | `0.0` | `0.0924` | `0.2361` | `0.1667` | `1.1917` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `1.2655` |
| `naive_graph_memory` | `0.2083` | `0.1389` | `0.0023` | `0.1389` | `0.4305` | `0.75` | `5.4339` |
| `clarks_nutcracker_graph` | `0.6667` | `0.4722` | `0.0347` | `0.466` | `0.0` | `1.0` | `10.435` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_zephyr_invoice`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1167`, stale `0.3333`, conflict `0.0`, latency `1.312` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2656` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2084` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2036` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1417`, stale `0.3333`, conflict `0.0`, latency `1.1216` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `1.0537` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1167`, stale `0.3333`, conflict `0.0`, latency `1.018` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1167`, stale `0.3333`, conflict `0.0`, latency `1.1346` ms
- `nutcracker_memory_research`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `0.0`, latency `1.2118` ms
- `elephant_context_runtime`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `1.1899` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.2911` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.2833`, stale `0.3333`, conflict `1.0`, latency `1.2903` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3692` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3321` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2669` ms
- `vendor_orion_procurement`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3204` ms
- `vendor_zephyr_invoice`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.1599` ms
- `customer_titan_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.0792` ms
- `customer_nova_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.0833` ms
- `demand_forecast_analytics`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.1938` ms
- `nutcracker_memory_research`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2785` ms
- `elephant_context_runtime`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.2918` ms
- `compliance_audit_eu`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.3973` ms
- `warehouse_robot_ops`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.4133` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.5591` ms
- `deploy_beta_staging`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.34` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.6667`, conflict `0.0`, latency `5.3345` ms
- `vendor_orion_procurement`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.3156` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `4.7692` ms
- `customer_titan_support`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.0`, conflict `1.0`, latency `4.7777` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.5`, conflict `0.0`, latency `5.0618` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.3333`, conflict `0.0`, latency `5.5056` ms
- `nutcracker_memory_research`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.8054` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `5.8914` ms
- `compliance_audit_eu`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `6.0561` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.5`, conflict `1.0`, latency `5.7908` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.6667`, relation_hit `0.0556`, usefulness `0.6667`, stale `0.0`, conflict `1.0`, latency `11.916` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.5181` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.2792` ms
- `vendor_orion_procurement`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.7139` ms
- `vendor_zephyr_invoice`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `8.989` ms
- `customer_titan_support`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `9.1562` ms
- `customer_nova_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.325`, stale `0.0`, conflict `1.0`, latency `10.0611` ms
- `demand_forecast_analytics`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.5652` ms
- `nutcracker_memory_research`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `10.3542` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `10.5187` ms
- `compliance_audit_eu`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `11.5053` ms
- `warehouse_robot_ops`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `10.6428` ms
