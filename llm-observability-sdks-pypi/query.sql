SELECT module, count(DISTINCT project) AS projects
FROM 'REFS'
WHERE module IN ('langfuse', 'langsmith', 'logfire', 'openinference', 'traceloop',
                 'weave', 'opik', 'agentops', 'braintrust', 'lmnr')
  -- leave out each SDK's own packages (langfuse-*, openinference-*) and the iflow-mcp copies
  AND NOT starts_with(lower(project), 'iflow-mcp')
  AND NOT starts_with(replace(replace(lower(project), '_', '-'), '.', '-') || '-', module || '-')
GROUP BY module
ORDER BY projects DESC;
