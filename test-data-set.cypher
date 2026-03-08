MERGE (ws:Workspace {id: 'ws.alpha'})
SET ws.name = 'Alpha Workspace', ws.description = 'Operational memory test workspace', ws.created_on = '2026-03-08';

MERGE (ada:Person {id: 'person.ada'})
SET ada.name = 'Ada Lovelace', ada.role = 'tech_lead', ada.team = 'platform';

MERGE (grace:Person {id: 'person.grace'})
SET grace.name = 'Grace Hopper', grace.role = 'engineering_manager', grace.team = 'platform';

MERGE (linus:Person {id: 'person.linus'})
SET linus.name = 'Linus Torvalds', linus.role = 'staff_engineer', linus.team = 'infra';

MATCH (p:Person), (ws:Workspace {id: 'ws.alpha'})
MERGE (p)-[:MEMBER_OF]->(ws);

MERGE (proj_api:Project {id: 'proj.memory-api'})
SET proj_api.name = 'Memory API', proj_api.status = 'active', proj_api.owner = 'person.ada';

MERGE (proj_ui:Project {id: 'proj.memory-ui'})
SET proj_ui.name = 'Memory UI', proj_ui.status = 'active', proj_ui.owner = 'person.grace';

MATCH (ws:Workspace {id: 'ws.alpha'}), (p:Project)
MERGE (p)-[:IN_WORKSPACE]->(ws);

MERGE (dec_1:Decision {id: 'decision.001'})
SET dec_1.title = 'Use FastAPI for memory endpoints', dec_1.status = 'accepted', dec_1.recorded_on = '2026-03-08';

MERGE (task_1:Task {id: 'task.001'})
SET task_1.title = 'Implement POST /v1/memory/remember', task_1.priority = 'high', task_1.status = 'done';

MERGE (task_2:Task {id: 'task.002'})
SET task_2.title = 'Implement POST /v1/memory/recall', task_2.priority = 'high', task_2.status = 'done';

MERGE (task_3:Task {id: 'task.003'})
SET task_3.title = 'Implement POST /v1/context/build', task_3.priority = 'high', task_3.status = 'in_progress';

MERGE (obs_1:Observation {id: 'observation.001'})
SET obs_1.summary = 'Recall ranking is sensitive to short ambiguous queries', obs_1.severity = 'medium', obs_1.recorded_on = '2026-03-08';

MERGE (risk_1:Risk {id: 'risk.001'})
SET risk_1.summary = 'Embedding provider outage blocks remember flow', risk_1.status = 'open', risk_1.severity = 'high';

MERGE (note_1:Note {id: 'note.001'})
SET note_1.content = 'Context bundles must include provenance references for every supporting item.', note_1.source = 'design-review', note_1.recorded_on = '2026-03-08';

MERGE (idea_1:Idea {id: 'idea.001'})
SET idea_1.title = 'Future graph-aware hybrid recall pass', idea_1.status = 'backlog';

MATCH (dec_1:Decision {id: 'decision.001'}), (proj_api:Project {id: 'proj.memory-api'})
MERGE (dec_1)-[:ABOUT]->(proj_api);

MATCH (dec_1:Decision {id: 'decision.001'}), (ada:Person {id: 'person.ada'})
MERGE (dec_1)-[:DECIDED_BY]->(ada);

MATCH (task_1:Task {id: 'task.001'}), (dec_1:Decision {id: 'decision.001'})
MERGE (task_1)-[:DERIVED_FROM]->(dec_1);

MATCH (task_2:Task {id: 'task.002'}), (dec_1:Decision {id: 'decision.001'})
MERGE (task_2)-[:DERIVED_FROM]->(dec_1);

MATCH (task_3:Task {id: 'task.003'}), (dec_1:Decision {id: 'decision.001'})
MERGE (task_3)-[:DERIVED_FROM]->(dec_1);

MATCH (task_1:Task {id: 'task.001'}), (ada:Person {id: 'person.ada'})
MERGE (ada)-[:ASSIGNED_TO]->(task_1);

MATCH (task_2:Task {id: 'task.002'}), (linus:Person {id: 'person.linus'})
MERGE (linus)-[:ASSIGNED_TO]->(task_2);

MATCH (task_3:Task {id: 'task.003'}), (grace:Person {id: 'person.grace'})
MERGE (grace)-[:ASSIGNED_TO]->(task_3);

MATCH (obs_1:Observation {id: 'observation.001'}), (proj_api:Project {id: 'proj.memory-api'})
MERGE (obs_1)-[:OBSERVED_IN]->(proj_api);

MATCH (obs_1:Observation {id: 'observation.001'}), (grace:Person {id: 'person.grace'})
MERGE (grace)-[:RECORDED]->(obs_1);

MATCH (risk_1:Risk {id: 'risk.001'}), (task_3:Task {id: 'task.003'})
MERGE (risk_1)-[:BLOCKS]->(task_3);

MATCH (note_1:Note {id: 'note.001'}), (dec_1:Decision {id: 'decision.001'})
MERGE (note_1)-[:REFERENCES]->(dec_1);

MATCH (note_1:Note {id: 'note.001'}), (proj_ui:Project {id: 'proj.memory-ui'})
MERGE (note_1)-[:ABOUT]->(proj_ui);

MATCH (task_1:Task {id: 'task.001'}), (proj_api:Project {id: 'proj.memory-api'})
MERGE (task_1)-[:FOR_PROJECT]->(proj_api);

MATCH (task_2:Task {id: 'task.002'}), (proj_api:Project {id: 'proj.memory-api'})
MERGE (task_2)-[:FOR_PROJECT]->(proj_api);

MATCH (task_3:Task {id: 'task.003'}), (proj_ui:Project {id: 'proj.memory-ui'})
MERGE (task_3)-[:FOR_PROJECT]->(proj_ui);

MATCH (p:Person)-[:ASSIGNED_TO]->(t:Task)
RETURN p.name AS owner, t.title AS task, t.status AS status;

MATCH (n)
RETURN count(n) AS total_nodes;
