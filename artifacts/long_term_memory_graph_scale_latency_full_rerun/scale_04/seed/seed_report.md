# Long-Term Memory Graph Demo Report

- Browser URL: http://127.0.0.1:7594/browser/
- Prefix: `graph-scale-s04-`
- Stored capsules: `1440`
- Graph nodes: `1440`
- Graph edges: `2440`

## Relation Counts

- `TEMPORAL_NEXT`: 1392
- `SCOPE_OVERLAP`: 436
- `CONFLICTS_WITH`: 240
- `REVISES`: 240
- `SAME_TASK`: 77
- `EVIDENCE_SUPPORTS`: 55

## Recall Samples

### deploy_alpha_prod
- Query: `service alpha deployment alice approval production rollout`
- Returned capsules: `12`
- Returned edges: `0`
- Summary head: `Subgraph theme: prod, cohort_01, approval, round_3.`
- Suppressed stale nodes: graph-scale-s04-deploy_alpha_prod-caps-006, graph-scale-s02-deploy_alpha_prod-caps-006
- Suppressed conflict nodes: graph-scale-s04-deploy_alpha_prod-caps-026

### deploy_beta_staging
- Query: `service beta staging release evidence validation rollout`
- Returned capsules: `8`
- Returned edges: `4`
- Summary head: `Subgraph theme: staging, cohort_01, release, deploy.`
- Suppressed stale nodes: graph-scale-s04-deploy_beta_staging-caps-008, graph-scale-s04-deploy_beta_staging-caps-009, graph-scale-s04-deploy_beta_staging-caps-007, graph-scale-s02-deploy_beta_staging-caps-008
- Suppressed conflict nodes: none

### api_gateway_patch
- Query: `api gateway patch waf regression validation security`
- Returned capsules: `12`
- Returned edges: `0`
- Summary head: `Subgraph theme: prod, cohort_01, security, patch.`
- Suppressed stale nodes: graph-scale-s04-api_gateway_patch-caps-006, graph-scale-s02-api_gateway_patch-caps-006
- Suppressed conflict nodes: graph-scale-s04-api_gateway_patch-caps-026, graph-scale-s02-api_gateway_patch-caps-026, graph-scale-s04-api_gateway_patch-caps-016

### vendor_orion_procurement
- Query: `vendor orion procurement certificate plant north sensor order`
- Returned capsules: `12`
- Returned edges: `0`
- Summary head: `Subgraph theme: cohort_01, procurement, vendor, plant.`
- Suppressed stale nodes: viz-demo-elephant_context_runtime-caps-002
- Suppressed conflict nodes: graph-scale-s02-vendor_orion_procurement-caps-013, graph-scale-s04-vendor_orion_procurement-caps-023, graph-scale-s04-vendor_orion_procurement-caps-013

### vendor_zephyr_invoice
- Query: `zephyr invoice reconciliation ledger duplicate charge finance`
- Returned capsules: `12`
- Returned edges: `2`
- Summary head: `Subgraph theme: cohort_01, finance, invoice, q2_close.`
- Suppressed stale nodes: graph-scale-s04-vendor_zephyr_invoice-caps-001, graph-scale-s04-vendor_zephyr_invoice-caps-010, graph-scale-s04-vendor_zephyr_invoice-caps-002, graph-scale-s02-vendor_zephyr_invoice-caps-001
- Suppressed conflict nodes: graph-scale-s04-vendor_zephyr_invoice-caps-011

### customer_titan_support
- Query: `customer titan p1 escalation sla breach support workaround`
- Returned capsules: `9`
- Returned edges: `5`
- Summary head: `Subgraph theme: cohort_01, support, incident, region_east.`
- Suppressed stale nodes: graph-scale-s04-customer_titan_support-caps-010, graph-scale-s04-customer_titan_support-caps-001, graph-scale-s02-customer_titan_support-caps-001
- Suppressed conflict nodes: none
