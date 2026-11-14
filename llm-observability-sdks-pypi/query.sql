SELECT module,
       count(DISTINCT project) AS projects
FROM 'REFS'
WHERE module IN ('langfuse', 'langsmith', 'logfire', 'openinference', 'traceloop',
                 'weave', 'opik', 'agentops', 'braintrust', 'lmnr')
  AND NOT starts_with(lower(project), 'iflow-mcp')
GROUP BY module
ORDER BY projects DESC;
