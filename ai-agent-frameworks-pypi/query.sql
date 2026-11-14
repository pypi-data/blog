SELECT CASE WHEN starts_with(module, 'langchain') THEN 'langchain_*' ELSE module END AS module,
       count(DISTINCT project) AS projects
FROM 'REFS'
WHERE (starts_with(module, 'langchain')
       OR module IN ('langgraph', 'pydantic_ai', 'crewai', 'llama_index', 'claude_agent_sdk',
                     'strands', 'dspy', 'deepagents', 'agno', 'smolagents', 'openai', 'anthropic'))
  AND NOT starts_with(lower(project), 'iflow-mcp')
GROUP BY 1
ORDER BY projects DESC;
