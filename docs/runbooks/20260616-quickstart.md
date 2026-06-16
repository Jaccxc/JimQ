# JimQ — 怎麼啟動(超簡版)

一律用 `make`。瀏覽器永遠開 **http://127.0.0.1:8080**。

```bash
make            # 看所有指令
```

## 最快看到東西(回測,不需金鑰)

```bash
make up         # 起全棧(首次會自動 build,等幾分鐘)
make exp        # 灌真歷史 + 跑一次 EMA 回測,自動重整儀表板
# 開 http://127.0.0.1:8080 → Backtest 頁,看真 K 線 + 進出場 marker
```

## 看 Binance testnet 真即時 / 下 paper 單(需 .env.afk 金鑰,已備妥)

```bash
make up                 # 先確保全棧在跑
make live               # 終端 A:接 testnet 真即時 K 線(不下單)
#   或 make paper       # 終端 A:testnet paper 下單(⛔ 假錢)
make reload             # 終端 B:跑一次,讓儀表板接上本次串流
# 開 http://127.0.0.1:8080 → Live 頁
```

> `make live` / `make paper` 會卡住前景持續跑(這是正常的,它在串流);
> 要停就在那個終端按 **Ctrl-C**。

## 其他常用

```bash
make logs           # 跟看 log(Ctrl-C 離開,不會停服務)
make ps             # 看服務狀態
make down           # 停全棧(資料保留)
make build          # 改了程式碼後重建映像
make full-restart   # 砍掉重練:down → build → up → logs
```

## 指令一覽

| 指令 | 做什麼 | 看哪頁 |
|---|---|---|
| `make up` | 起全棧 | — |
| `make exp` | 跑回測實驗 | Backtest |
| `make live` | testnet 真即時 K 線(不下單) | Live |
| `make paper` | testnet paper 下單(⛔ 假錢) | Live |
| `make reload` | live/paper 後讓儀表板接上 | — |
| `make logs` / `ps` / `down` | log / 狀態 / 停 | — |
| `make build` / `full-restart` | 重建 | — |

## 卡住了?

| 症狀 | 處置 |
|---|---|
| Live 頁有 badge 但圖空白 | `make live`/`paper` 有在跑嗎?跑一次 `make reload`。 |
| `-2015 Invalid API-key` | testnet 金鑰問題,到 testnet.binancefuture.com 重產(寫進 `.env.afk`)。 |
| docker 沒權限 | 見 `DEV_CONTRACT_AFK.md`(已設好,通常重登一次生效)。 |

---

進階細節(風控旗標、kill switch、對帳、研究管線、架構圖):
[`20260616-live-data-testnet.md`](./20260616-live-data-testnet.md)、
[`20260616-research-demo.md`](./20260616-research-demo.md)、根目錄 [`README.md`](../../README.md)。
