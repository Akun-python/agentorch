:param prefix => 'viz-demo-';

// 1) Full demo graph overview
MATCH p=(a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN p
LIMIT 300;

// 2) Node and edge counts by relation type
MATCH (n:MemoryCapsule)
WHERE n.capsule_id STARTS WITH $prefix
OPTIONAL MATCH (n)-[r]->(m:MemoryCapsule)
WHERE m.capsule_id STARTS WITH $prefix
RETURN count(DISTINCT n) AS node_count, count(DISTINCT r) AS edge_count;

MATCH (a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN type(r) AS relation_type, count(*) AS relation_count
ORDER BY relation_count DESC, relation_type;

// 3) A focused cluster view for one scenario
MATCH p=(a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.task_family = 'viz-demo-deploy_alpha_prod'
  AND b.task_family = 'viz-demo-deploy_alpha_prod'
RETURN p
LIMIT 200;

// 4) Stale low-confidence demo nodes
MATCH (n:MemoryCapsule)
WHERE n.capsule_id STARTS WITH $prefix
  AND n.confidence < 0.65
RETURN n
ORDER BY n.created_at ASC
LIMIT 100;

// 5) Conflict and revision chains
MATCH p=(a:MemoryCapsule)-[r:CONFLICTS_WITH|REVISES]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN p
LIMIT 200;
