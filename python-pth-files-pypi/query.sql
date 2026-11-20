-- PyPI projects whose latest release has a .pth file with an import line,
-- most downloaded first (downloads_30d is empty outside the 60,000 most downloaded)
SELECT t.project, t.pth, p.downloads_30d
FROM 'PTH' t JOIN 'PROJECTS' p USING (project)
ORDER BY p.downloads_30d DESC NULLS LAST, t.project, t.pth
LIMIT 12;
