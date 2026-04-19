# Long-Term Memory Graph Baseline Benchmark

- Prefix: `benchmark-stability-seed03-`
- Cases: `12`
- First-screen node budget: `6`
- First-screen edge budget: `12`

## Aggregate Comparison

| Baseline | recall@k | relevance | relation_hit | usefulness | stale_injection | conflict_success | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_long_term_memory` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0` | `0.0002` |
| `vector_memory` | `0.1042` | `0.0833` | `0.0` | `0.0792` | `0.1667` | `0.4167` | `2.6579` |
| `flat_summary_memory` | `1.0` | `0.8333` | `0.0` | `0.75` | `0.0` | `1.0` | `2.9976` |
| `naive_graph_memory` | `0.375` | `0.25` | `0.0069` | `0.25` | `0.3194` | `0.9167` | `11.4071` |
| `clarks_nutcracker_graph` | `0.6042` | `0.4305` | `0.0371` | `0.4257` | `0.0` | `1.0` | `22.7185` |

## Case Rows

### no_long_term_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0004` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_orion_procurement`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `vendor_zephyr_invoice`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0005` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `nutcracker_memory_research`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `elephant_context_runtime`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0002` ms
- `compliance_audit_eu`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `0.0001` ms

### vector_memory
- `deploy_alpha_prod`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `1.5261` ms
- `deploy_beta_staging`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `2.5365` ms
- `api_gateway_patch`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `2.1555` ms
- `vendor_orion_procurement`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `2.2391` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `3.8035` ms
- `customer_titan_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `2.956` ms
- `customer_nova_support`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.0`, conflict `0.0`, latency `2.7348` ms
- `demand_forecast_analytics`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.1667`, conflict `0.0`, latency `3.9008` ms
- `nutcracker_memory_research`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `2.3092` ms
- `elephant_context_runtime`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `2.8009` ms
- `compliance_audit_eu`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.1667`, conflict `1.0`, latency `2.4831` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1167`, stale `0.3333`, conflict `0.0`, latency `2.4496` ms

### flat_summary_memory
- `deploy_alpha_prod`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `1.7405` ms
- `deploy_beta_staging`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.7975` ms
- `api_gateway_patch`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `3.0199` ms
- `vendor_orion_procurement`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.6532` ms
- `vendor_zephyr_invoice`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.9603` ms
- `customer_titan_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `4.4562` ms
- `customer_nova_support`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.7339` ms
- `demand_forecast_analytics`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `3.4944` ms
- `nutcracker_memory_research`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.8548` ms
- `elephant_context_runtime`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.958` ms
- `compliance_audit_eu`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `2.5823` ms
- `warehouse_robot_ops`: recall@k `1.0`, relevance `0.8333`, relation_hit `0.0`, usefulness `0.75`, stale `0.0`, conflict `1.0`, latency `3.7202` ms

### naive_graph_memory
- `deploy_alpha_prod`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `9.0337` ms
- `deploy_beta_staging`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `13.44` ms
- `api_gateway_patch`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `9.4176` ms
- `vendor_orion_procurement`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `10.5514` ms
- `vendor_zephyr_invoice`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `12.1282` ms
- `customer_titan_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.5`, conflict `1.0`, latency `10.5221` ms
- `customer_nova_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `12.0652` ms
- `demand_forecast_analytics`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `13.4621` ms
- `nutcracker_memory_research`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.3333`, conflict `1.0`, latency `11.4695` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `11.0107` ms
- `compliance_audit_eu`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.3333`, conflict `1.0`, latency `12.5601` ms
- `warehouse_robot_ops`: recall@k `0.0`, relevance `0.0`, relation_hit `0.0`, usefulness `0.0`, stale `0.3333`, conflict `0.0`, latency `11.2244` ms

### clarks_nutcracker_graph
- `deploy_alpha_prod`: recall@k `0.5`, relevance `0.6667`, relation_hit `0.0556`, usefulness `0.6667`, stale `0.0`, conflict `1.0`, latency `23.4907` ms
- `deploy_beta_staging`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `20.6565` ms
- `api_gateway_patch`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `17.7516` ms
- `vendor_orion_procurement`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `22.7779` ms
- `vendor_zephyr_invoice`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `27.333` ms
- `customer_titan_support`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0278`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `22.93` ms
- `customer_nova_support`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.325`, stale `0.0`, conflict `1.0`, latency `26.942` ms
- `demand_forecast_analytics`: recall@k `0.75`, relevance `0.5`, relation_hit `0.0556`, usefulness `0.4917`, stale `0.0`, conflict `1.0`, latency `22.7064` ms
- `nutcracker_memory_research`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `21.1085` ms
- `elephant_context_runtime`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.0278`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `24.1351` ms
- `compliance_audit_eu`: recall@k `0.5`, relevance `0.3333`, relation_hit `0.1111`, usefulness `0.3333`, stale `0.0`, conflict `1.0`, latency `20.5094` ms
- `warehouse_robot_ops`: recall@k `0.25`, relevance `0.1667`, relation_hit `0.0`, usefulness `0.1667`, stale `0.0`, conflict `1.0`, latency `22.2808` ms
