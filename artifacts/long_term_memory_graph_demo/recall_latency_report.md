# Long-Term Memory Graph Recall Latency Report

- Prefix: `viz-demo-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `360` nodes / `12525` edges
- Warmup rounds: `1`
- Measured recalls: `60`

## Overall

- `recall()` mean / median / p95: `87.024` / `86.013` / `99.646` ms
- `recall()` throughput: `11.491` qps
- `fetch_capsule_details()` mean / median / p95: `3.849` / `3.869` / `4.52` ms
- `fetch_capsule_details()` throughput: `259.808` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `89.271` ms, detail mean `3.839` ms, avg nodes `12`, avg edges `24`
- `deploy_beta_staging`: recall mean `86.137` ms, detail mean `3.415` ms, avg nodes `12`, avg edges `24`
- `api_gateway_patch`: recall mean `81.851` ms, detail mean `3.721` ms, avg nodes `12`, avg edges `24`
- `vendor_orion_procurement`: recall mean `88.174` ms, detail mean `3.684` ms, avg nodes `12`, avg edges `22`
- `vendor_zephyr_invoice`: recall mean `86.166` ms, detail mean `3.973` ms, avg nodes `12`, avg edges `24`
- `customer_titan_support`: recall mean `89.888` ms, detail mean `4.112` ms, avg nodes `12`, avg edges `24`
- `customer_nova_support`: recall mean `88.027` ms, detail mean `4.236` ms, avg nodes `12`, avg edges `13.6`
- `demand_forecast_analytics`: recall mean `90.599` ms, detail mean `3.96` ms, avg nodes `12`, avg edges `23`
- `nutcracker_memory_research`: recall mean `85.712` ms, detail mean `3.785` ms, avg nodes `12`, avg edges `24`
- `elephant_context_runtime`: recall mean `85.144` ms, detail mean `3.895` ms, avg nodes `12`, avg edges `18`
- `compliance_audit_eu`: recall mean `87.161` ms, detail mean `3.688` ms, avg nodes `12`, avg edges `24`
- `warehouse_robot_ops`: recall mean `86.159` ms, detail mean `3.882` ms, avg nodes `12`, avg edges `24`
