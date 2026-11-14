SELECT module, count(DISTINCT project) AS projects
FROM (
  SELECT project,
         CASE WHEN starts_with(module, 'langchain') THEN 'langchain_*' ELSE module END AS module
  FROM 'REFS'
  WHERE starts_with(module, 'langchain')
     OR module IN ('langgraph', 'pydantic_ai', 'crewai', 'llama_index', 'claude_agent_sdk',
                   'strands', 'dspy', 'deepagents', 'agno', 'smolagents', 'openai', 'anthropic')
)
-- leave out each tool's own packages (langchain-*, crewai-*) and the iflow-mcp copies
WHERE NOT starts_with(lower(project), 'iflow-mcp')
  AND NOT starts_with(replace(replace(lower(project), '_', '-'), '.', '-') || '-',
                      replace(replace(module, '_*', ''), '_', '-') || '-')
GROUP BY module
ORDER BY projects DESC;
