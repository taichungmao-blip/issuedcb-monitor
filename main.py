import pandas as pd
import yfinance as yf
import requests
import datetime
import os
import json

# ==========================================
# 🎯 戰情室 V12.0 (GitHub Actions 版)
# ==========================================

class CBSniperBot:
    def __init__(self):
        # 讀取環境變數中的 Discord Webhook
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK")
        
        # 鄭大四大條件
        self.MIN_AVG_VOL = 50       
        self.MIN_PRICE = 110.0      
        self.MAX_PRICE = 150.0      
        self.DROP_RATE = 0.05       
        
        self.end_date = datetime.date.today()
        # GitHub Runner 有時會有時差，確保抓取範圍夠寬
        self.start_date = self.end_date - datetime.timedelta(days=50)

    def send_discord_message(self, content):
        if not self.webhook_url:
            print("❌ 未設定 DISCORD_WEBHOOK，無法發送通知。")
            return
        
        data = {
            "username": "鄭大戰情室",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2910/2910795.png", # 機器人頭像
            "content": content
        }
        try:
            requests.post(self.webhook_url, json=data)
        except Exception as e:
            print(f"發送 Discord 失敗: {e}")

    def get_all_active_cb_tickers(self):
        print("🕷️ 正在從櫃買中心抓取清單...")
        url = "https://www.tpex.org.tw/web/bond/tradeinfo/cb/cb_daily_result.php?l=zh-tw&o=json"
        try:
            res = requests.get(url)
            data = res.json()
            raw_list = data['aaData']
            cb_list = []
            for item in raw_list:
                if len(item[0]) == 5: 
                    cb_list.append({"code": item[0], "name": item[1]})
            return cb_list
        except Exception as e:
            print(f"❌ 抓取名單失敗: {e}")
            return []

    def run(self):
        cb_list = self.get_all_active_cb_tickers()
        if not cb_list: return

        print(f"📉 分析中... 共 {len(cb_list)} 檔")
        
        targets = []
        tickers_map = {f"{item['code']}.TWO": item for item in cb_list}
        tickers_list = list(tickers_map.keys())
        
        # 分批下載避免錯誤
        chunk_size = 50
        for i in range(0, len(tickers_list), chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            try:
                data = yf.download(chunk, start=self.start_date, end=self.end_date, group_by='ticker', progress=False)
                
                for ticker in chunk:
                    if len(chunk) == 1: df = data
                    else: 
                        try: df = data[ticker]
                        except: continue
                    
                    df = df.dropna()
                    if len(df) < 10: continue

                    last_close = df['Close'].iloc[-1]
                    
                    # 條件篩選
                    if not (self.MIN_PRICE <= last_close <= self.MAX_PRICE): continue
                    
                    avg_vol = df['Volume'].tail(10).mean()
                    # yfinance 有時回傳股數有時回傳張數，這裡做個簡單防呆
                    # 假設 < 10000 可能是張數 (不太可能均量1萬張)，> 10000 可能是股數
                    # 統一換算成張數顯示
                    display_vol = avg_vol
                    if avg_vol > 10000: # 判定為股
                        avg_vol_verify = avg_vol
                        display_vol = int(avg_vol / 1000)
                    else: # 判定為張
                         avg_vol_verify = avg_vol * 1000
                         display_vol = int(avg_vol)

                    if avg_vol_verify < 50000: continue # 小於50張 (50000股)

                    try:
                        price_3days_ago = df['Close'].iloc[-4]
                        drop_pct = (price_3days_ago - last_close) / price_3days_ago
                    except: continue

                    if drop_pct > self.DROP_RATE:
                        original = tickers_map[ticker]
                        targets.append(f"**{original['code']} {original['name']}**\n收盤: {last_close:.1f} | 跌幅: -{drop_pct*100:.2f}% | 均量: {display_vol}張")
            except Exception as e:
                pass

        # 發送結果
        if targets:
            message = "🎯 **鄭大短波段狙擊手報告** 🎯\n發現符合「急跌+有量+甜蜜點」標的：\n\n" + "\n".join(targets)
            self.send_discord_message(message)
            print("✅ 通知已發送")
        else:
            print("💤 今日無符合標的，不打擾用戶")
            # 也可以選擇發送一個 "今日無標的" 的通知，看個人喜好
            # self.send_discord_message("💤 本日掃描完畢，無符合策略之標的。")

if __name__ == "__main__":
    bot = CBSniperBot()
    bot.run()
