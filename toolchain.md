# Toolchain Probe Result

- Probe time: 2026-10-29 01:24:16
- Probe script: scripts\00_probe.bat
- Note: versions below come from actual `-version` / `-v` output, not from directory names.

Component | Status | Absolute path | Version | Requirement | Note
--- | --- | --- | --- | --- | ---
JDK 8 | OK | D:\develop\java-se-8u44-ri\bin\java.exe | 1.8.0_44 | 8u44+ | meets 8u44+
JDK 17 | OK | D:\develop\jdk-17.0.0.1\bin\java.exe | 17.0.0.1 | 17.0.x | major version 17
Maven | OK | D:\tools\apache-maven-3.9.12\bin\mvn.cmd | 3.9.12 | 3.6+ | meets 3.6+
Node.js | MISMATCH | C:\Program Files\nodejs\node.exe | 24.14.1 | 16.20 or 18.x | outside 16.20 / 18.x
MySQL | OK | C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe | 8.0.46 | 5.7 or 8.0 | meets 5.7 / 8.0
Redis | MISSING | - | - | 5.0+ | redis-server.exe not found
Nginx | OK | C:\Users\HZR\Desktop\若依系统\nginx\nginx.exe | 1.26.3 | 1.20+ | meets 1.20+

## Status legend

- `MISSING`: component not found on this machine. Per the spec, do not download or install it automatically; ask for confirmation first.
- `LOW` / `MISMATCH`: executable found, but the actual version does not meet the deployment spec under `docs/`.
- JDK detection is based on the major version printed by an actual `java -version` run; Maven detection uses `mvn.cmd` on Windows.

