SELECT sdk, count(DISTINCT project) AS projects
FROM (
  SELECT project,
         CASE WHEN module LIKE 'langchain%' THEN 'langchain'
              WHEN module = 'google' THEN 'google-genai'
              ELSE module END AS sdk
  FROM 'hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d/refs.parquet'
  WHERE module IN ('openai', 'anthropic', 'litellm', 'ollama', 'mcp')
     OR module LIKE 'langchain%'
     OR name = 'google.genai' OR name LIKE 'google.genai.%'
)
JOIN 'hf://datasets/pypi-data/py-code@9d81d70d6519d77f4dee4811b3e3a5d88379c17d/projects.parquet' USING (project)
WHERE upload_time >= '2025-11-13'
GROUP BY sdk
ORDER BY projects DESC;
