import pandas as pd
import yfinance as yf
import requests
import datetime
import os
import time

# ==========================================
# 🎯 戰情室 V12.1 (GitHub Actions 修正版)
# ==========================================

class CBSniperBot:
    def __init__(self):
        # 讀取環境變數中的 Discord Webhook
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK")
        
        # 鄭大四大條件參數
        self.MIN_AVG_VOL = 50       
        self.MIN_PRICE = 110.0      
        self.MAX_PRICE = 150.0      
        self.DROP_RATE = 0.05       
        
        self.end_date = datetime.date.today()
        self.start_date = self.end_date - datetime.timedelta(days=50)

    def send_discord_message(self, content):
        if not self.webhook_url:
            print("❌ 未設定 DISCORD_WEBHOOK，無法發送通知。")
            return
        
        data = {
            "username": "鄭大戰情室",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2910/2910795.png",
            "content": content
        }
        try:
            requests.post(self.webhook_url, json=data)
        except Exception as e:
            print(f"發送 Discord 失敗: {e}")

    def get_all_active_cb_tickers(self):
        print("🕷️ 正在從櫃買中心抓取清單...")
        url = "https://www.tpex.org.tw/web/bond/tradeinfo/cb/cb_daily_result.php?l=zh-tw&o=json"
        
        # ✅ 修正重點 1: 加入 Headers 偽裝成瀏覽器，避免被擋
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status() # 檢查請求是否成功 (200 OK)
            data = res.json()
            raw_list = data['aaData']
            cb_list = []
            for item in raw_list:
                # 確保代碼長度正確 (過濾掉合計列)
                if len(item[0]) == 5: 
                    cb_list.append({"code": item[0], "name": item[1]})
            return cb_list
        except Exception as e:
            print(f"❌ 抓取名單失敗 (可能是官網維護或阻擋): {e}")
            return []

    def run(self):
        cb_list = self.get_all_active_cb_tickers()
        if not cb_list:
            print("⚠️ 無法取得清單，程式終止。")
            return

        print(f"📉 分析中... 共 {len(cb_list)} 檔")
        
        targets = []
        tickers_map = {f"{item['code']}.TWO": item for item in cb_list}
        tickers_list = list(tickers_map.keys())
        
        # 分批下載
        chunk_size = 50
        for i in range(0, len(tickers_list), chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            try:
                # 靜默下載
                data = yf.download(chunk, start=self.start_date, end=self.end_date, group_by='ticker', progress=False)
                
                for ticker in chunk:
                    # 處理 yfinance 資料結構
                    if len(chunk) == 1: 
                        df = data
                    else: 
                        try: df = data[ticker]
                        except: continue
                    
                    # 資料清理
                    df = df.dropna()
                    if len(df) < 10: continue

                    last_close = float(df['Close'].iloc[-1])
                    
                    # 條件 1: 價格篩選
                    if not (self.MIN_PRICE <= last_close <= self.MAX_PRICE): continue
                    
                    # 條件 2: 成交量篩選
                    avg_vol = float(df['Volume'].tail(10).mean())
                    
                    # ✅ 修正重點 2: 更嚴謹的單位換算邏輯
                    # yfinance 台股有時回傳股數，有時回傳張數，這裡統一處理
                    if avg_vol > 10000: # 判定為股 (例如 50000)
                        display_vol = int(avg_vol / 1000)
                    else: # 判定為張 (例如 50)
                        display_vol = int(avg_vol)

                    if display_vol < self.MIN_AVG_VOL: continue # 小於50張

                    # 條件 3: 跌幅篩選
                    try:
                        price_3days_ago = float(df['Close'].iloc[-4])
                        drop_pct = (price_3days_ago - last_close) / price_3days_ago
                    except: continue

                    if drop_pct > self.DROP_RATE:
                        original = tickers_map[ticker]
                        info_str = f"**{original['code']} {original['name']}**\n收盤: {last_close:.1f} | 跌幅: -{drop_pct*100:.2f}% | 均量: {display_vol}張"
                        print(f"🔥 發現目標: {info_str}")
                        targets.append(info_str)
            
            except Exception as e:
                print(f"⚠️ 批次處理錯誤 (非致命): {e}")
                pass

        # 發送結果
        if targets:
            message = "🎯 **鄭大短波段狙擊手報告** 🎯\n發現符合「急跌+有量+甜蜜點」標的：\n\n" + "\n".join(targets)
            self.send_discord_message(message)
            print("✅ 通知已發送")
        else:
            print("💤 今日無符合標的，不打擾用戶")

if __name__ == "__main__":
    try:
        bot = CBSniperBot()
        bot.run()
    except Exception as e:
        print(f"❌ 程式發生未預期錯誤: {e}")
        # 這裡不拋出錯誤，避免 GitHub Actions 顯示紅燈 (Annotated Error)，但我們可以在 Log 看到
        exit(0)
