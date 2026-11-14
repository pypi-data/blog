SELECT sdk, count(DISTINCT project) AS projects
FROM (
  SELECT project,
         CASE WHEN module LIKE 'langchain%' THEN 'langchain'
              WHEN module = 'google' THEN 'google-genai'
              ELSE module END AS sdk
  FROM 'REFS'
  WHERE module IN ('openai', 'anthropic', 'litellm', 'ollama', 'mcp')
     OR module LIKE 'langchain%'
     OR name = 'google.genai' OR name LIKE 'google.genai.%'
)
JOIN 'PROJECTS' USING (project)
WHERE upload_time >= '2025-11-13'
  -- leave out each SDK's own packages (langchain-*, mcp-*) and the iflow-mcp copies
  AND NOT starts_with(lower(project), 'iflow-mcp')
  AND NOT (replace(replace(lower(project), '_', '-'), '.', '-') = sdk
           OR starts_with(replace(replace(lower(project), '_', '-'), '.', '-'), sdk || '-'))
GROUP BY sdk
ORDER BY projects DESC;
