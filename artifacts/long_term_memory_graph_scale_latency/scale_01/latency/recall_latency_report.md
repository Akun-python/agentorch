# Long-Term Memory Graph Recall Latency Report

- Prefix: `graph-scale-s01-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `360` nodes / `3012` edges
- Warmup rounds: `2`
- Measured recalls: `120`

## Overall

- `recall()` mean / median / p95: `55.008` / `54.41` / `64.95` ms
- `recall()` throughput: `18.179` qps
- `fetch_capsule_details()` mean / median / p95: `2.872` / `2.743` / `3.264` ms
- `fetch_capsule_details()` throughput: `348.189` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `55.183` ms, detail mean `2.791` ms, avg nodes `12`, avg edges `3`
- `deploy_beta_staging`: recall mean `56.572` ms, detail mean `2.733` ms, avg nodes `12`, avg edges `10`
- `api_gateway_patch`: recall mean `52.92` ms, detail mean `2.637` ms, avg nodes `12`, avg edges `0`
- `vendor_orion_procurement`: recall mean `58.323` ms, detail mean `2.762` ms, avg nodes `12`, avg edges `6`
- `vendor_zephyr_invoice`: recall mean `53.947` ms, detail mean `2.873` ms, avg nodes `12`, avg edges `11`
- `customer_titan_support`: recall mean `55.915` ms, detail mean `2.927` ms, avg nodes `12`, avg edges `2`
- `customer_nova_support`: recall mean `54.917` ms, detail mean `2.803` ms, avg nodes `12`, avg edges `0`
- `demand_forecast_analytics`: recall mean `55.86` ms, detail mean `2.62` ms, avg nodes `12`, avg edges `0`
- `nutcracker_memory_research`: recall mean `55.815` ms, detail mean `4.18` ms, avg nodes `12`, avg edges `15`
- `elephant_context_runtime`: recall mean `55.215` ms, detail mean `2.691` ms, avg nodes `12`, avg edges `21`
- `compliance_audit_eu`: recall mean `52.844` ms, detail mean `2.628` ms, avg nodes `12`, avg edges `21`
- `warehouse_robot_ops`: recall mean `52.585` ms, detail mean `2.818` ms, avg nodes `12`, avg edges `18`
