# LIRE

一個輕量型的小型音樂機器人

> [!WARNING]  
> 建議只裝在一個伺服器就好了 (否則請見 [這一條](#改造成大型機器人))

# FAQ

### Q1. 為什麼選擇 LIRE？

- 我知道現在 Discord 有很多優秀的音樂機器人，但是每一台機器人都有缺點，而自己架的機器人相對比較穩定，且所有功能都能客製化。

### Q2. LIRE 就沒有缺點嗎？

- 有。但這也是你自己寫出來的。

### Q3. 為什麼要做 LIRE？

- ~~懶得邀其他機器人~~ 我不知道。

### Q4. 爛 Bot

- 這個項目原本就是骨架，要讓開發者(你)自己完善。

# REPL

你要先參考 [這裡](https://github.com/AWeirdDev/replit-ffmpeg) 下載 ffmpeg

# 部屬

```py
pip install -r requirements.txt
python main.py
```

這是要怎麼失敗。

# 改造成大型機器人

請把 `MusicQueue` 中的函數 的前面加上 `GuildID`

```py
self.now['1135507433624698962']['...']
# 我只是範例 你記得要改
```

`trigger` 也差不多，如果有效能或斷斷續續的問題 建議你多塞一點 `asyncio`。

# 貢獻

這個項目花了我大約三天的時間，其實還有很多可以改進的地方，如果你開 PR，我會很開心。
