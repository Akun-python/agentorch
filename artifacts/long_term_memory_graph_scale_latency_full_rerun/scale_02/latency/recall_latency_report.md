# Long-Term Memory Graph Recall Latency Report

- Prefix: `graph-scale-s02-`
- Neo4j: `Neo4j Kernel 5.26.24 (community)`
- Graph size: `720` nodes / `3045` edges
- Warmup rounds: `2`
- Measured recalls: `60`

## Overall

- `recall()` mean / median / p95: `98.422` / `97.642` / `126.376` ms
- `recall()` throughput: `10.16` qps
- `fetch_capsule_details()` mean / median / p95: `3.672` / `3.674` / `4.185` ms
- `fetch_capsule_details()` throughput: `272.331` qps

## Per Scenario

- `deploy_alpha_prod`: recall mean `108.212` ms, detail mean `3.616` ms, avg nodes `12`, avg edges `19`
- `deploy_beta_staging`: recall mean `95.608` ms, detail mean `3.599` ms, avg nodes `12`, avg edges `4`
- `api_gateway_patch`: recall mean `106.185` ms, detail mean `3.498` ms, avg nodes `12`, avg edges `0`
- `vendor_orion_procurement`: recall mean `106.757` ms, detail mean `3.789` ms, avg nodes `12`, avg edges `6`
- `vendor_zephyr_invoice`: recall mean `95.513` ms, detail mean `3.851` ms, avg nodes `12`, avg edges `4`
- `customer_titan_support`: recall mean `87.855` ms, detail mean `3.851` ms, avg nodes `12`, avg edges `4`
- `customer_nova_support`: recall mean `96.408` ms, detail mean `3.378` ms, avg nodes `12`, avg edges `13`
- `demand_forecast_analytics`: recall mean `83.973` ms, detail mean `3.547` ms, avg nodes `12`, avg edges `4`
- `nutcracker_memory_research`: recall mean `92.689` ms, detail mean `3.564` ms, avg nodes `12`, avg edges `4`
- `elephant_context_runtime`: recall mean `105.03` ms, detail mean `4.085` ms, avg nodes `12`, avg edges `8.2`
- `compliance_audit_eu`: recall mean `103.088` ms, detail mean `3.687` ms, avg nodes `12`, avg edges `3`
- `warehouse_robot_ops`: recall mean `99.744` ms, detail mean `3.596` ms, avg nodes `12`, avg edges `4`
