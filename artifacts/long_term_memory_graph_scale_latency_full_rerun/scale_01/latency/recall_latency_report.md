# Long-Term Memory Graph Recall Latency Report

- Prefix: `graph-scale-s01-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `360` nodes / `3012` edges
- Warmup rounds: `2`
- Measured recalls: `60`

## Overall

- `recall()` mean / median / p95: `99.08` / `95.971` / `120.244` ms
- `recall()` throughput: `10.093` qps
- `fetch_capsule_details()` mean / median / p95: `3.759` / `3.797` / `4.572` ms
- `fetch_capsule_details()` throughput: `266.028` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `97.22` ms, detail mean `3.499` ms, avg nodes `12`, avg edges `3`
- `deploy_beta_staging`: recall mean `104.05` ms, detail mean `4.11` ms, avg nodes `12`, avg edges `10`
- `api_gateway_patch`: recall mean `111.003` ms, detail mean `3.726` ms, avg nodes `12`, avg edges `0`
- `vendor_orion_procurement`: recall mean `102.167` ms, detail mean `3.873` ms, avg nodes `12`, avg edges `6`
- `vendor_zephyr_invoice`: recall mean `95.594` ms, detail mean `3.518` ms, avg nodes `12`, avg edges `11`
- `customer_titan_support`: recall mean `94.076` ms, detail mean `3.714` ms, avg nodes `12`, avg edges `2`
- `customer_nova_support`: recall mean `91.048` ms, detail mean `3.669` ms, avg nodes `12`, avg edges `0`
- `demand_forecast_analytics`: recall mean `96.519` ms, detail mean `3.77` ms, avg nodes `12`, avg edges `0`
- `nutcracker_memory_research`: recall mean `98.938` ms, detail mean `3.89` ms, avg nodes `12`, avg edges `15`
- `elephant_context_runtime`: recall mean `97.868` ms, detail mean `3.873` ms, avg nodes `12`, avg edges `21`
- `compliance_audit_eu`: recall mean `100.128` ms, detail mean `3.813` ms, avg nodes `12`, avg edges `21`
- `warehouse_robot_ops`: recall mean `100.349` ms, detail mean `3.649` ms, avg nodes `12`, avg edges `18`
