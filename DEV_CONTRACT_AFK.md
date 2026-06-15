# DEV_CONTRACT_AFK — JimQ 開發鐵律契約

> 本檔是 ultra-tdd AFK 開發的**單一真相來源**。每個 dev/verify agent 開工前必須 Read 全文,並把所有鐵律轉述給自己 summon 的子 agent。
> 2026-06-16 建立。base 工作分支 = `main`。

## 0. 已驗證環境

| 項目 | 值 |
|---|---|
| repo | `Jaccxc/JimQ`(PRIVATE),本機路徑 `/home/jacc/projects/JimQ` |
| 主要工作分支 | **`main`**(本 repo 無 dev/stg/prd;feature 從 main 開,merge 回 main) |
| Python | **3.12**(`/usr/bin/python3.12`;uv 0.11.21) |
| 套件管理 | **uv**(workspace;`research` 獨立 venv) |
| Docker | 可用(免 sudo;daemon 已可連)。docker compose v2 可用 |
| Redis | **本機 docker-compose**(localhost;Nautilus message bus + cache 用不同 DB index) |
| Postgres | **本機 docker-compose**(localhost) |
| gh | host = github.com,已登入(account `Jaccxc`) |
| 憑證 | sudo / postgres 密碼見 **gitignored `.env.afk`**(本機 dev 慣例)。**絕不把密碼 commit 進任何檔案**。dev agent 由 manager 經 prompt 取得 |
| sudo | 可用(`echo "$SUDO_PASS" | sudo -S <cmd>`)。**僅在真正必要的基礎設施步驟才用**(極罕見;docker 已修好) |
| push | **使用者已明示授權** push 到 `origin/main` 與 feature 分支 |

## 1. 鐵律(硬性,違反即錯)

1. **分支**:從 `main` 開 `feat/<key>-<slug>`,完成後以 `git merge --no-ff` 回 `main`。**絕不 squash**(保留完整 commit 歷史)。本 repo 無 dev/stg/prd 分支。
2. **DB migration**:改 schema **先**手寫 alembic revision(`uv run alembic revision -m "msg"`,**不要 --autogenerate**),**再** `uv run alembic upgrade head`。**永不直接對 DB 下 DDL/DML**。(alembic 工作目錄依 api 套件實際結構,見 repo 結構文件。)
3. **建 DB / role**:唯一允許直接 psql 的情境 = 建立新 database 或 role(`PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U postgres`)。其餘不得用 psql 改任何東西。
4. **localhost only**:任何 psql / DB 連線只能連 **localhost**。嚴禁連任何非 localhost 資料庫。
5. **Redis**:用**本機 docker-compose Redis**(localhost)。Nautilus message bus/streams 與 boilerplate cache 用**不同 Redis DB index** 隔離。(覆寫 ultra-tdd 預設的遠端 Redis —— JimQ 定案 local-first。)
6. **Kafka / 其他 broker**:本期不需要。若未來需要,用 docker 跑,不假設外部現成 broker。
7. **深度委派**:任務清楚有界就交給子 agent;雜事(裝 deps、lint、查 legacy、跑 build)深度委派。不為並行而並行。
8. **TDD**:必須 TDD 垂直切片(tracer bullet):一個測試 → 一段最小實作 → 重複。RED→GREEN→(全綠後)refactor。測試只驗證「行為(透過 public interface)」,不驗證實作細節。不要先寫一堆測試再寫一堆實作。
9. **轉述規則**:summon 的每個子 agent 都要被提醒上述全部鐵律。
10. **Schema 正規化**:禁止把結構化資料塞進 JSON 欄位;正確正規化(3NF、拆表、索引、`timestamptz`、精確數值型別)。JSONB 只給本質非結構化 payload。
11. **列舉欄位用 VARCHAR + 應用層 enum**:**不用 DB 原生 enum**(禁 `CREATE TYPE`/`postgresql.ENUM`/`SAEnum(create_type=...)`);DB 存 `VARCHAR(32)` 大寫契約字面值,enum 約束放應用層(TypeDecorator)。
12. **完全不用外鍵(no FK)**:任何表都不建 `FOREIGN KEY`(禁 `ForeignKey`/`ForeignKeyConstraint`/`ondelete`);關聯欄位保留 + 一般索引,一致性由應用層維護。

## 2. 凍結契約 / 設計真相來源(用路徑引用,不複製內文)

- 決策定案:`docs/design/20260616-1830-decisions-confirmed.md`
- 專案結構:`docs/design/20260616-1845-repo-structure-final.md`
- PRD(Phase 1):GitHub issue **#1**
- 切片卡:#2–#10(依賴見各 issue body 的 *Blocked by*)
- 研究背景:`docs/research/*`

## 3. Issue 收尾規則

- 每張卡 TDD 完成,在對應 GitHub issue 留言實作結果(`gh issue comment <iid> --repo Jaccxc/JimQ`):做了什麼、測試涵蓋、分支/commit、驗證方式。
- 無待人工事項即關卡(`gh issue close <iid>`);有待人工事項則留言但不關。
- **不**動 parent PRD(#1)。

## 4. 授權範圍

- ✅ commit / push 到 `origin/main` 與 feature 分支(使用者明示授權)。
- ✅ sudo(密碼在 `.env.afk`),僅限真正必要的基礎設施步驟。
- ✅ 全 AFK:所有設計分岔由 manager 依第 2 節凍結契約自主拍板,不喚醒使用者。
- ❌ 不碰使用者機器上與本專案無關的東西;不連非 localhost DB;不把密碼寫進任何 commit。
