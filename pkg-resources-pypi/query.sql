SELECT p.project,
       p.downloads_30d,
       CAST(p.upload_time AS DATE) AS last_release,
       string_agg(DISTINCT r.name, ', ' ORDER BY r.name) AS names_used
FROM 'REFS' r JOIN 'PROJECTS' p USING (project)
WHERE r.module = 'pkg_resources'
  AND r.name LIKE 'pkg\_resources.%' ESCAPE '\'
  AND p.project <> 'setuptools'
  AND p.upload_time >= '2026-02-08'
GROUP BY ALL
ORDER BY p.downloads_30d DESC
LIMIT 10;
