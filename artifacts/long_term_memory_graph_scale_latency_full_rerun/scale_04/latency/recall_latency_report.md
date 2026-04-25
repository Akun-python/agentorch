# Long-Term Memory Graph Recall Latency Report

- Prefix: `graph-scale-s04-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `1440` nodes / `2440` edges
- Warmup rounds: `2`
- Measured recalls: `60`

## Overall

- `recall()` mean / median / p95: `91.602` / `96.244` / `142.437` ms
- `recall()` throughput: `10.917` qps
- `fetch_capsule_details()` mean / median / p95: `3.674` / `3.655` / `4.029` ms
- `fetch_capsule_details()` throughput: `272.183` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `109.388` ms, detail mean `3.699` ms, avg nodes `12`, avg edges `0`
- `deploy_beta_staging`: recall mean `47.13` ms, detail mean `3.804` ms, avg nodes `8`, avg edges `4`
- `api_gateway_patch`: recall mean `121.341` ms, detail mean `3.682` ms, avg nodes `12`, avg edges `0`
- `vendor_orion_procurement`: recall mean `108.599` ms, detail mean `3.613` ms, avg nodes `12`, avg edges `0`
- `vendor_zephyr_invoice`: recall mean `85.016` ms, detail mean `3.622` ms, avg nodes `12`, avg edges `2`
- `customer_titan_support`: recall mean `56.506` ms, detail mean `3.557` ms, avg nodes `9`, avg edges `5`
- `customer_nova_support`: recall mean `111.587` ms, detail mean `3.861` ms, avg nodes `12`, avg edges `0`
- `demand_forecast_analytics`: recall mean `78.886` ms, detail mean `3.658` ms, avg nodes `12`, avg edges `2`
- `nutcracker_memory_research`: recall mean `106.392` ms, detail mean `3.622` ms, avg nodes `12`, avg edges `4`
- `elephant_context_runtime`: recall mean `134.019` ms, detail mean `3.691` ms, avg nodes `12`, avg edges `0`
- `compliance_audit_eu`: recall mean `90.082` ms, detail mean `3.569` ms, avg nodes `12`, avg edges `2`
- `warehouse_robot_ops`: recall mean `50.272` ms, detail mean `3.712` ms, avg nodes `8`, avg edges `4`
