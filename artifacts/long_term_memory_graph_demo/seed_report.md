# Long-Term Memory Graph Demo Report

- Browser URL: http://127.0.0.1:7594/browser/
- Prefix: `viz-demo-`
- Stored capsules: `360`
- Graph nodes: `360`
- Graph edges: `12525`

## Relation Counts

- `CONFLICTS_WITH`: 3288
- `SAME_TASK`: 2930
- `SCOPE_OVERLAP`: 2930
- `REVISES`: 2741
- `TEMPORAL_NEXT`: 348
- `EVIDENCE_SUPPORTS`: 288

## Recall Samples

### deploy_alpha_prod
- Query: `service alpha deployment alice approval production rollout`
- Returned capsules: `12`
- Returned edges: `24`
- Summary head: `Subgraph theme: prod, approval, round_3, deploy.`
- Suppressed stale nodes: viz-demo-deploy_alpha_prod-caps-006, viz-demo-deploy_alpha_prod-caps-003, viz-demo-deploy_alpha_prod-caps-005, viz-demo-deploy_alpha_prod-caps-002, viz-demo-deploy_alpha_prod-caps-009, viz-demo-deploy_alpha_prod-caps-007, viz-demo-deploy_alpha_prod-caps-008, viz-demo-deploy_alpha_prod-caps-010, viz-demo-deploy_alpha_prod-caps-001, viz-demo-deploy_alpha_prod-caps-004
- Suppressed conflict nodes: none

### deploy_beta_staging
- Query: `service beta staging release evidence validation rollout`
- Returned capsules: `12`
- Returned edges: `24`
- Summary head: `Subgraph theme: staging, release, round_3, deploy.`
- Suppressed stale nodes: viz-demo-deploy_beta_staging-caps-002, viz-demo-deploy_beta_staging-caps-005, viz-demo-deploy_beta_staging-caps-007, viz-demo-deploy_beta_staging-caps-009, viz-demo-deploy_beta_staging-caps-003, viz-demo-deploy_beta_staging-caps-010, viz-demo-deploy_beta_staging-caps-006, viz-demo-deploy_beta_staging-caps-008, viz-demo-deploy_beta_staging-caps-001, viz-demo-deploy_beta_staging-caps-004
- Suppressed conflict nodes: none

### api_gateway_patch
- Query: `api gateway patch waf regression validation security`
- Returned capsules: `12`
- Returned edges: `24`
- Summary head: `Subgraph theme: prod, security, patch, gateway.`
- Suppressed stale nodes: viz-demo-api_gateway_patch-caps-001, viz-demo-api_gateway_patch-caps-008, viz-demo-api_gateway_patch-caps-004, viz-demo-api_gateway_patch-caps-002, viz-demo-api_gateway_patch-caps-009, viz-demo-api_gateway_patch-caps-006, viz-demo-api_gateway_patch-caps-007, viz-demo-api_gateway_patch-caps-010, viz-demo-api_gateway_patch-caps-005, viz-demo-api_gateway_patch-caps-003
- Suppressed conflict nodes: none

### vendor_orion_procurement
- Query: `vendor orion procurement certificate plant north sensor order`
- Returned capsules: `12`
- Returned edges: `22`
- Summary head: `Subgraph theme: procurement, vendor, plant, plant_north.`
- Suppressed stale nodes: viz-demo-vendor_orion_procurement-caps-003, viz-demo-vendor_orion_procurement-caps-008, viz-demo-vendor_orion_procurement-caps-010, viz-demo-vendor_orion_procurement-caps-006, viz-demo-vendor_orion_procurement-caps-004, viz-demo-vendor_orion_procurement-caps-009, viz-demo-vendor_orion_procurement-caps-005, viz-demo-vendor_orion_procurement-caps-007, viz-demo-vendor_orion_procurement-caps-001, viz-demo-vendor_orion_procurement-caps-002
- Suppressed conflict nodes: viz-demo-vendor_orion_procurement-caps-023

### vendor_zephyr_invoice
- Query: `zephyr invoice reconciliation ledger duplicate charge finance`
- Returned capsules: `12`
- Returned edges: `24`
- Summary head: `Subgraph theme: finance, invoice, q2_close, round_3.`
- Suppressed stale nodes: viz-demo-vendor_zephyr_invoice-caps-005, viz-demo-vendor_zephyr_invoice-caps-003, viz-demo-vendor_zephyr_invoice-caps-010, viz-demo-vendor_zephyr_invoice-caps-002, viz-demo-vendor_zephyr_invoice-caps-007, viz-demo-vendor_zephyr_invoice-caps-004, viz-demo-vendor_zephyr_invoice-caps-008, viz-demo-vendor_zephyr_invoice-caps-006, viz-demo-vendor_zephyr_invoice-caps-009, viz-demo-vendor_zephyr_invoice-caps-001
- Suppressed conflict nodes: none

### customer_titan_support
- Query: `customer titan p1 escalation sla breach support workaround`
- Returned capsules: `12`
- Returned edges: `24`
- Summary head: `Subgraph theme: support, incident, region_east, p1.`
- Suppressed stale nodes: viz-demo-customer_titan_support-caps-001, viz-demo-customer_titan_support-caps-007, viz-demo-customer_titan_support-caps-010, viz-demo-customer_titan_support-caps-006, viz-demo-customer_titan_support-caps-005, viz-demo-customer_titan_support-caps-004, viz-demo-customer_titan_support-caps-003, viz-demo-customer_titan_support-caps-008, viz-demo-customer_titan_support-caps-002, viz-demo-customer_titan_support-caps-009
- Suppressed conflict nodes: none
