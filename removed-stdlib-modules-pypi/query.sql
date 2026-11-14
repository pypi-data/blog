SELECT p.project,
       p.downloads_30d,
       CAST(p.upload_time AS DATE) AS last_release,
       string_agg(DISTINCT r.module, ', ' ORDER BY r.module) AS removed_modules
FROM 'REFS' r JOIN 'PROJECTS' p USING (project)
WHERE r.name = r.module
  AND r.module IN ('distutils', 'imp', 'asyncore', 'asynchat', 'smtpd',
                   'aifc', 'audioop', 'cgi', 'cgitb', 'chunk', 'crypt', 'imghdr',
                   'lib2to3', 'mailcap', 'msilib', 'nis', 'nntplib', 'ossaudiodev',
                   'pipes', 'sndhdr', 'spwd', 'sunau', 'telnetlib', 'uu', 'xdrlib')
  AND p.upload_time < '2024-11-13'
GROUP BY ALL
ORDER BY p.downloads_30d DESC
LIMIT 10;
