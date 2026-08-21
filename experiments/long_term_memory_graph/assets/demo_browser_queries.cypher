:param prefix => 'viz-demo-';

// 1) 查看演示图谱全貌
MATCH p=(a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN p
LIMIT 300;

// 2) 统计演示节点数量和边数量
MATCH (n:MemoryCapsule)
WHERE n.capsule_id STARTS WITH $prefix
OPTIONAL MATCH (n)-[r]->(m:MemoryCapsule)
WHERE m.capsule_id STARTS WITH $prefix
RETURN count(DISTINCT n) AS node_count, count(DISTINCT r) AS edge_count;

// 按关系类型统计边，确认 TEMPORAL_NEXT / REVISES / CONFLICTS_WITH 等是否写入。
MATCH (a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN type(r) AS relation_type, count(*) AS relation_count
ORDER BY relation_count DESC, relation_type;

// 3) 聚焦某个任务族，查看单个场景簇
MATCH p=(a:MemoryCapsule)-[r]->(b:MemoryCapsule)
WHERE a.task_family = 'viz-demo-deploy_alpha_prod'
  AND b.task_family = 'viz-demo-deploy_alpha_prod'
RETURN p
LIMIT 200;

// 4) 查看低置信度候选节点，用于验证陈旧/低置信压制
MATCH (n:MemoryCapsule)
WHERE n.capsule_id STARTS WITH $prefix
  AND n.confidence < 0.65
RETURN n
ORDER BY n.created_at ASC
LIMIT 100;

// 5) 查看冲突和修订链路
MATCH p=(a:MemoryCapsule)-[r:CONFLICTS_WITH|REVISES]->(b:MemoryCapsule)
WHERE a.capsule_id STARTS WITH $prefix
  AND b.capsule_id STARTS WITH $prefix
RETURN p
LIMIT 200;
