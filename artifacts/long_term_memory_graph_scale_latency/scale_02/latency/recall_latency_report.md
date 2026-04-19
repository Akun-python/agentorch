# Long-Term Memory Graph Recall Latency Report

- Prefix: `graph-scale-s02-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `720` nodes / `3045` edges
- Warmup rounds: `2`
- Measured recalls: `120`

## Overall

- `recall()` mean / median / p95: `55.521` / `53.706` / `71.473` ms
- `recall()` throughput: `18.011` qps
- `fetch_capsule_details()` mean / median / p95: `2.703` / `2.676` / `3.159` ms
- `fetch_capsule_details()` throughput: `369.959` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `61.912` ms, detail mean `2.703` ms, avg nodes `12`, avg edges `19`
- `deploy_beta_staging`: recall mean `52.345` ms, detail mean `2.737` ms, avg nodes `12`, avg edges `4`
- `api_gateway_patch`: recall mean `57.472` ms, detail mean `2.741` ms, avg nodes `12`, avg edges `0`
- `vendor_orion_procurement`: recall mean `61.254` ms, detail mean `2.754` ms, avg nodes `12`, avg edges `6`
- `vendor_zephyr_invoice`: recall mean `55.447` ms, detail mean `2.651` ms, avg nodes `12`, avg edges `4`
- `customer_titan_support`: recall mean `50.439` ms, detail mean `2.613` ms, avg nodes `12`, avg edges `4`
- `customer_nova_support`: recall mean `53.017` ms, detail mean `2.567` ms, avg nodes `12`, avg edges `13`
- `demand_forecast_analytics`: recall mean `51.052` ms, detail mean `2.689` ms, avg nodes `12`, avg edges `4`
- `nutcracker_memory_research`: recall mean `52.44` ms, detail mean `2.843` ms, avg nodes `12`, avg edges `4`
- `elephant_context_runtime`: recall mean `58.549` ms, detail mean `2.63` ms, avg nodes `12`, avg edges `10.1`
- `compliance_audit_eu`: recall mean `54.359` ms, detail mean `2.728` ms, avg nodes `12`, avg edges `3`
- `warehouse_robot_ops`: recall mean `57.966` ms, detail mean `2.778` ms, avg nodes `12`, avg edges `4`
