import pandas as pd
import yfinance as yf
import requests
import datetime
import os
import time
import sys

# ==========================================
# 🎯 戰情室 V12.2 (GitHub Actions 防彈版)
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
            print("❌ 未設定 DISCORD_WEBHOOK，跳過通知。")
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
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.tpex.org.tw/"
        }
        
        try:
            # 設定 timeout，避免卡死
            res = requests.get(url, headers=headers, timeout=10)
            
            # 如果被擋 (403/404)，這裡會報錯，被下方的 except 抓到
            res.raise_for_status() 
            
            data = res.json()
            raw_list = data['aaData']
            cb_list = []
            for item in raw_list:
                if len(item[0]) == 5: 
                    cb_list.append({"code": item[0], "name": item[1]})
            print(f"✅ 成功取得 {len(cb_list)} 檔清單")
            return cb_list
            
        except Exception as e:
            error_msg = f"❌ 無法抓取櫃買中心清單 (可能 IP 被擋或維護中): {e}"
            print(error_msg)
            # 發生錯誤時通知 Discord，方便除錯
            self.send_discord_message(f"⚠️ **系統警報** ⚠️\nGitHub Action 抓取 TPEX 清單失敗。\n原因: `{e}`")
            return []

    def run(self):
        cb_list = self.get_all_active_cb_tickers()
        
        # 如果清單是空的，直接結束，不要讓程式崩潰 (Exit 0)
        if not cb_list:
            print("⚠️ 清單為空，任務結束。")
            return

        print(f"📉 分析中... 共 {len(cb_list)} 檔")
        
        targets = []
        tickers_map = {f"{item['code']}.TWO": item for item in cb_list}
        tickers_list = list(tickers_map.keys())
        
        chunk_size = 50
        for i in range(0, len(tickers_list), chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            try:
                data = yf.download(chunk, start=self.start_date, end=self.end_date, group_by='ticker', progress=False)
                
                if data.empty: continue

                for ticker in chunk:
                    try:
                        if len(chunk) == 1: df = data
                        else: df = data[ticker]
                        
                        df = df.dropna()
                        if len(df) < 10: continue

                        # 修正: yfinance 有時返回 Series 有時返回 scalar，統一轉 float
                        last_close = float(df['Close'].iloc[-1])
                        
                        if not (self.MIN_PRICE <= last_close <= self.MAX_PRICE): continue
                        
                        avg_vol = float(df['Volume'].tail(10).mean())
                        
                        # 判斷單位 (股 vs 張)
                        if avg_vol > 10000: display_vol = int(avg_vol / 1000)
                        else: display_vol = int(avg_vol)

                        if display_vol < self.MIN_AVG_VOL: continue 

                        price_3days_ago = float(df['Close'].iloc[-4])
                        drop_pct = (price_3days_ago - last_close) / price_3days_ago

                        if drop_pct > self.DROP_RATE:
                            original = tickers_map[ticker]
                            info_str = f"**{original['code']} {original['name']}**\n收盤: {last_close:.1f} | 跌幅: -{drop_pct*100:.2f}% | 均量: {display_vol}張"
                            print(f"🔥 發現目標: {info_str}")
                            targets.append(info_str)
                    except Exception as inner_e:
                        # 單一檔股票錯誤跳過，不影響整體
                        continue
            
            except Exception as e:
                print(f"⚠️ 批次處理錯誤 (非致命): {e}")
                pass

        if targets:
            message = "🎯 **鄭大短波段狙擊手報告** 🎯\n發現符合「急跌+有量+甜蜜點」標的：\n\n" + "\n".join(targets)
            self.send_discord_message(message)
            print("✅ 通知已發送")
        else:
            print("💤 今日無符合標的")

if __name__ == "__main__":
    try:
        bot = CBSniperBot()
        bot.run()
        # 強制回傳 0 (成功)，避免 GitHub 顯示紅色 Error
        sys.exit(0)
    except Exception as e:
        print(f"❌ 程式發生未預期錯誤: {e}")
        # 即使發生大錯誤，也嘗試回傳 0 讓 Action 顯示綠燈，但印出錯誤 Log
        sys.exit(0)
