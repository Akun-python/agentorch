# Long-Term Memory Graph Demo Report

- Browser URL: http://127.0.0.1:7574/browser/
- Prefix: `graph-scale-s02-`
- Stored capsules: `720`
- Graph nodes: `720`
- Graph edges: `3045`

## Relation Counts

- `SCOPE_OVERLAP`: 697
- `TEMPORAL_NEXT`: 696
- `CONFLICTS_WITH`: 624
- `REVISES`: 624
- `SAME_TASK`: 323
- `EVIDENCE_SUPPORTS`: 81

## Recall Samples

### deploy_alpha_prod
- Query: `service alpha deployment alice approval production rollout`
- Returned capsules: `12`
- Returned edges: `19`
- Summary head: `Subgraph theme: prod, approval, round_3, cohort_01.`
- Suppressed stale nodes: graph-scale-s02-deploy_alpha_prod-caps-006, graph-scale-s02-deploy_alpha_prod-caps-001
- Suppressed conflict nodes: graph-scale-s02-deploy_alpha_prod__cohort_02-caps-025, graph-scale-s02-deploy_alpha_prod__cohort_02-caps-022

### deploy_beta_staging
- Query: `service beta staging release evidence validation rollout`
- Returned capsules: `12`
- Returned edges: `4`
- Summary head: `Subgraph theme: staging, cohort_01, release, round_3.`
- Suppressed stale nodes: graph-scale-s02-deploy_beta_staging-caps-008, graph-scale-s02-deploy_beta_staging-caps-001
- Suppressed conflict nodes: graph-scale-s02-deploy_beta_staging-caps-018

### api_gateway_patch
- Query: `api gateway patch waf regression validation security`
- Returned capsules: `12`
- Returned edges: `0`
- Summary head: `Subgraph theme: prod, cohort_01, security, patch.`
- Suppressed stale nodes: graph-scale-s02-api_gateway_patch-caps-006, graph-scale-s02-api_gateway_patch-caps-001
- Suppressed conflict nodes: graph-scale-s02-api_gateway_patch-caps-016, graph-scale-s02-api_gateway_patch-caps-026, graph-scale-s02-api_gateway_patch-caps-021

### vendor_orion_procurement
- Query: `vendor orion procurement certificate plant north sensor order`
- Returned capsules: `12`
- Returned edges: `6`
- Summary head: `Subgraph theme: procurement, vendor, plant, cohort_01.`
- Suppressed stale nodes: viz-demo-vendor_orion_procurement-caps-005, viz-demo-vendor_orion_procurement-caps-002, viz-demo-vendor_orion_procurement-caps-001, viz-demo-vendor_orion_procurement-caps-010, viz-demo-vendor_orion_procurement-caps-008, viz-demo-vendor_orion_procurement-caps-007, viz-demo-vendor_orion_procurement-caps-009, viz-demo-vendor_orion_procurement-caps-006, viz-demo-vendor_orion_procurement-caps-003, viz-demo-vendor_orion_procurement-caps-004, graph-scale-s01-vendor_orion_procurement-caps-003, graph-scale-s01-vendor_orion_procurement-caps-005, graph-scale-s01-vendor_orion_procurement-caps-010, graph-scale-s01-vendor_orion_procurement-caps-008, graph-scale-s01-compliance_audit_eu-caps-006
- Suppressed conflict nodes: graph-scale-s02-vendor_orion_procurement-caps-013, viz-demo-vendor_orion_procurement-caps-018, viz-demo-vendor_orion_procurement-caps-020, viz-demo-vendor_orion_procurement-caps-015, graph-scale-s02-vendor_orion_procurement-caps-023

### vendor_zephyr_invoice
- Query: `zephyr invoice reconciliation ledger duplicate charge finance`
- Returned capsules: `12`
- Returned edges: `4`
- Summary head: `Subgraph theme: cohort_01, finance, invoice, q2_close.`
- Suppressed stale nodes: graph-scale-s02-vendor_zephyr_invoice-caps-010, graph-scale-s02-vendor_zephyr_invoice-caps-006, graph-scale-s02-vendor_zephyr_invoice-caps-001
- Suppressed conflict nodes: graph-scale-s02-vendor_zephyr_invoice-caps-011

### customer_titan_support
- Query: `customer titan p1 escalation sla breach support workaround`
- Returned capsules: `12`
- Returned edges: `4`
- Summary head: `Subgraph theme: cohort_01, support, incident, region_east.`
- Suppressed stale nodes: graph-scale-s02-customer_titan_support-caps-010, graph-scale-s02-customer_titan_support-caps-001
- Suppressed conflict nodes: graph-scale-s02-customer_titan_support-caps-011
