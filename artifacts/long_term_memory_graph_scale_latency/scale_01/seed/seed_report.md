# Long-Term Memory Graph Demo Report

- Browser URL: http://127.0.0.1:7574/browser/
- Prefix: `graph-scale-s01-`
- Stored capsules: `360`
- Graph nodes: `360`
- Graph edges: `3012`

## Relation Counts

- `SAME_TASK`: 642
- `SCOPE_OVERLAP`: 642
- `CONFLICTS_WITH`: 626
- `REVISES`: 626
- `TEMPORAL_NEXT`: 348
- `EVIDENCE_SUPPORTS`: 128

## Recall Samples

### deploy_alpha_prod
- Query: `service alpha deployment alice approval production rollout`
- Returned capsules: `12`
- Returned edges: `3`
- Summary head: `Subgraph theme: prod, approval, deploy, alpha.`
- Suppressed stale nodes: graph-scale-s01-deploy_alpha_prod-caps-006, graph-scale-s01-deploy_alpha_prod-caps-007, graph-scale-s01-deploy_alpha_prod-caps-005, viz-demo-deploy_alpha_prod-caps-006
- Suppressed conflict nodes: graph-scale-s01-deploy_alpha_prod-caps-026

### deploy_beta_staging
- Query: `service beta staging release evidence validation rollout`
- Returned capsules: `12`
- Returned edges: `10`
- Summary head: `Subgraph theme: staging, release, round_3, deploy.`
- Suppressed stale nodes: graph-scale-s01-deploy_beta_staging-caps-008, graph-scale-s01-deploy_beta_staging-caps-007, graph-scale-s01-deploy_beta_staging-caps-009, viz-demo-deploy_beta_staging-caps-008
- Suppressed conflict nodes: graph-scale-s01-deploy_beta_staging-caps-023, graph-scale-s01-deploy_beta_staging-caps-018, graph-scale-s01-deploy_beta_staging-caps-024

### api_gateway_patch
- Query: `api gateway patch waf regression validation security`
- Returned capsules: `12`
- Returned edges: `0`
- Summary head: `Subgraph theme: prod, security, patch, gateway.`
- Suppressed stale nodes: graph-scale-s01-api_gateway_patch-caps-006, graph-scale-s01-api_gateway_patch-caps-005, graph-scale-s01-api_gateway_patch-caps-007, viz-demo-api_gateway_patch-caps-006
- Suppressed conflict nodes: graph-scale-s01-api_gateway_patch-caps-026, graph-scale-s01-api_gateway_patch-caps-016

### vendor_orion_procurement
- Query: `vendor orion procurement certificate plant north sensor order`
- Returned capsules: `12`
- Returned edges: `6`
- Summary head: `Subgraph theme: procurement, vendor, plant, plant_north.`
- Suppressed stale nodes: viz-demo-vendor_orion_procurement-caps-008, viz-demo-vendor_orion_procurement-caps-007, viz-demo-vendor_orion_procurement-caps-002, viz-demo-vendor_orion_procurement-caps-010, viz-demo-vendor_orion_procurement-caps-004, viz-demo-vendor_orion_procurement-caps-001, viz-demo-vendor_orion_procurement-caps-003, viz-demo-vendor_orion_procurement-caps-009, viz-demo-vendor_orion_procurement-caps-006, viz-demo-vendor_orion_procurement-caps-005, graph-scale-s01-vendor_orion_procurement-caps-003
- Suppressed conflict nodes: graph-scale-s01-vendor_orion_procurement-caps-013, graph-scale-s01-vendor_orion_procurement-caps-023

### vendor_zephyr_invoice
- Query: `zephyr invoice reconciliation ledger duplicate charge finance`
- Returned capsules: `12`
- Returned edges: `11`
- Summary head: `Subgraph theme: finance, invoice, q2_close, round_3.`
- Suppressed stale nodes: viz-demo-vendor_zephyr_invoice-caps-001, viz-demo-vendor_zephyr_invoice-caps-003, viz-demo-vendor_zephyr_invoice-caps-008, viz-demo-vendor_zephyr_invoice-caps-004, graph-scale-s01-vendor_zephyr_invoice-caps-010, viz-demo-vendor_zephyr_invoice-caps-009, viz-demo-vendor_zephyr_invoice-caps-006, viz-demo-vendor_zephyr_invoice-caps-007, viz-demo-vendor_zephyr_invoice-caps-005, viz-demo-vendor_zephyr_invoice-caps-002, viz-demo-vendor_zephyr_invoice-caps-010, graph-scale-s01-vendor_zephyr_invoice-caps-001
- Suppressed conflict nodes: graph-scale-s01-vendor_zephyr_invoice-caps-011

### customer_titan_support
- Query: `customer titan p1 escalation sla breach support workaround`
- Returned capsules: `12`
- Returned edges: `2`
- Summary head: `Subgraph theme: support, incident, region_east, round_3.`
- Suppressed stale nodes: viz-demo-customer_titan_support-caps-001, viz-demo-customer_titan_support-caps-003, viz-demo-customer_titan_support-caps-004, viz-demo-customer_titan_support-caps-006, viz-demo-customer_titan_support-caps-002, graph-scale-s01-customer_titan_support-caps-010, viz-demo-customer_titan_support-caps-007, viz-demo-customer_titan_support-caps-009, viz-demo-customer_titan_support-caps-010, viz-demo-customer_titan_support-caps-008, viz-demo-customer_titan_support-caps-005, graph-scale-s01-customer_titan_support-caps-001
- Suppressed conflict nodes: graph-scale-s01-customer_titan_support-caps-011
