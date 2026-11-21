"""Neo4j 초기 비밀번호 변경 — CredentialsExpired 상태 해소.

set-initial-password 가 데이터베이스 첫 시작 이전에만 동작하는데, 5.x 는
설치 직후 자동으로 system DB 초기화하므로 기본값 'neo4j' 가 expired 상태로 남는다.
시연 PoC 한정 — 운영 도입 시 별도 비밀번호 정책 적용.
"""
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
NEW_PW = "sherpa-poc-2026"

drv = GraphDatabase.driver(URI, auth=("neo4j", "neo4j"))
with drv.session(database="system") as s:
    s.run(f"ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO '{NEW_PW}'")
print("password changed")
drv.close()

drv2 = GraphDatabase.driver(URI, auth=("neo4j", NEW_PW))
with drv2.session() as s:
    row = s.run("RETURN 1 AS ok, datetime() AS now").single()
    print("verify OK", dict(row))
drv2.close()
