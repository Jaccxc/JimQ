# jimq-core

JimQ 共用套件:engine 與 api(及 research)共用的 DTO schema、特徵庫、常數。

- `schemas.py` — 共用 DTO(engine/api 共用)
- `features.py` — 共用特徵庫(engine Strategy 與 research env 共用,消除 train/serve skew)
- `constants.py` — 共用常數(含 Redis DB index 隔離契約)

S0 為佔位骨架,後續切片填實。
