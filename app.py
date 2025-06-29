import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import uuid

# 資料檔路徑
USER_PATH = "data/users.csv"
SCHED_PATH = "data/schedule.csv"
LOG_PATH = "data/clock_logs.csv"

# 輔助函式
def load_users():
    return pd.read_csv(USER_PATH)

def load_schedule():
    return pd.read_csv(SCHED_PATH)

def save_schedule(df):
    df.to_csv(SCHED_PATH, index=False)

def log_clock(username, status):
    now = datetime.now()
    today = now.date()
    new_log = pd.DataFrame([{
        "username": username,
        "date": today,
        "time": now.strftime("%H:%M:%S"),
        "status": status
    }])
    try:
        logs = pd.read_csv(LOG_PATH)
        logs = pd.concat([logs, new_log], ignore_index=True)
    except FileNotFoundError:
        logs = new_log
    logs.to_csv(LOG_PATH, index=False)

def check_late(username):
    today = datetime.now().strftime("%Y-%m-%d")
    sched = load_schedule()
    user_sched = sched[(sched['username'] == username) & (sched['date'] == today)]
    if user_sched.empty:
        return False, "今天沒有排班"
    start_time_str = user_sched.iloc[0]['start_time']
    scheduled = datetime.strptime(start_time_str, "%H:%M")
    actual = datetime.now()
    scheduled = actual.replace(hour=scheduled.hour, minute=scheduled.minute, second=0, microsecond=0)
    if (actual - scheduled).total_seconds() > 300:
        return True, f"⚠️ 遲到！預定 {start_time_str}，實際 {actual.strftime('%H:%M')}"
    else:
        return False, f"✅ 準時打卡（{actual.strftime('%H:%M')}）"
    

def send_telegram_message(message, token, chat_id):
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            st.success("✅ Telegram 訊息已發送")
        else:
            st.warning(f"⚠️ 發送失敗：{response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"❌ 發送錯誤：{e}")



# 頁面設定
st.set_page_config(page_title="員工打卡系統", layout="centered")
st.title("⏱️ 員工打卡系統")

# 登入機制
users = load_users()
username = st.selectbox("選擇帳號", users["username"].tolist())
password = st.text_input("輸入密碼", type="password")

user_row = users[(users["username"] == username) & (users["password"] == password)]

if not user_row.empty:
    role = user_row.iloc[0]["role"]
    st.success(f"登入成功：{username}（{role}）")

    # 員工介面
    if role == "employee":
        st.subheader("🕒 打卡操作")
        if st.button("上班打卡"):
            log_clock(username, "in")
            is_late, msg = check_late(username)
            st.info(msg)

        if st.button("下班打卡"):
            log_clock(username, "out")
            st.success("下班打卡成功")

        # === 工作清單 + 評分 ===
        # 基本資料
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = pd.read_csv("data/tasks.csv")
        task_logs_path = "data/task_logs.csv"
        score_logs_path = "data/score_logs.csv"
        adjustments_path = "data/score_adjustments.csv"

        # 讀取使用者任務紀錄
        try:
            task_logs = pd.read_csv(task_logs_path)
        except:
            task_logs = pd.DataFrame(columns=["username", "date", "task_id", "completed"])

        today_logs = task_logs[(task_logs["username"] == username) & (task_logs["date"] == today)]

        # 表單開始
        st.subheader("📋 今日工作任務")
        with st.form("task_form"):
            st.write("請勾選你今天完成的任務，然後點選下方按鈕儲存")

            checked_list = []
            for i, row in tasks[tasks["is_routine"] == True].iterrows():
                task_id = row["task_id"]
                task_name = row["task_name"]
                score = row["score"]

                prev = today_logs[today_logs["task_id"] == task_id]
                checked = False if prev.empty else prev.iloc[0]["completed"]
                checked_list.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "score": score,
                    "checked": st.checkbox(f"{task_name}（{score}分）", value=checked, key=f"task_{task_id}")
                })

            submitted = st.form_submit_button("💾 儲存任務完成狀態")

        # 如果有按下 submit，就儲存並計算分數
        if submitted:
            new_logs = []
            base_score = 0
            for log in checked_list:
                new_logs.append({
                    "username": username,
                    "date": today,
                    "task_id": log["task_id"],
                    "completed": log["checked"]
                })
                if log["checked"]:
                    base_score += log["score"]

            # 覆寫舊紀錄
            updated_logs = task_logs[~((task_logs["username"] == username) & (task_logs["date"] == today))]
            updated_logs = pd.concat([updated_logs, pd.DataFrame(new_logs)], ignore_index=True)
            updated_logs.to_csv(task_logs_path, index=False)

            st.success("任務完成狀態已儲存！")

            # 讀取加分
            try:
                adj_df = pd.read_csv(adjustments_path)
                adj = adj_df[(adj_df["username"] == username) & (adj_df["date"] == today)]
                adj_score = adj["score"].sum() if not adj.empty else 0
            except:
                adj_score = 0

            total_score = base_score + adj_score

            # 儲存 score_logs
            try:
                score_logs = pd.read_csv(score_logs_path)
            except:
                score_logs = pd.DataFrame(columns=["username", "date", "base_score", "adjusted_score", "total_score"])

            score_logs = score_logs[~((score_logs["username"] == username) & (score_logs["date"] == today))]
            score_logs = pd.concat([score_logs, pd.DataFrame([{
                "username": username,
                "date": today,
                "base_score": base_score,
                "adjusted_score": adj_score,
                "total_score": total_score
            }])], ignore_index=True)
            score_logs.to_csv(score_logs_path, index=False)

            # 顯示分數
            st.metric("🎯 今日得分", f"{total_score} 分", help=f"基礎分數 {base_score} + 管理員調整 {adj_score}")

            # 顯示一週平均
            score_logs["date"] = pd.to_datetime(score_logs["date"])
            last_7 = score_logs[(score_logs["username"] == username) & (score_logs["date"] >= datetime.now() - timedelta(days=7))]

            if not last_7.empty:
                avg_score = last_7["total_score"].mean()
                st.metric("📊 最近 7 天平均分數", f"{avg_score:.1f} 分")
                st.line_chart(last_7.set_index("date")["total_score"])
            else:
                st.info("目前尚無足夠資料顯示過去 7 天分數")

        st.subheader("🚨 問題回報系統")

        ISSUE_TYPES = ["機台", "客人", "店面", "其他"]
        issue_logs_path = "data/issue_logs.csv"
        uploads_dir = "uploads"

        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        # 表單區
        with st.form("report_issue_form"):
            issue_type = st.selectbox("問題類型", ISSUE_TYPES)
            desc = st.text_area("請簡要描述問題")
            # photo = st.file_uploader("上傳相關照片（可選）", type=["jpg", "jpeg", "png"])
            uploaded_photos = st.file_uploader("上傳最多 5 張圖片", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            if uploaded_photos and len(uploaded_photos) > 5:
                st.warning("請勿上傳超過 5 張圖片！")

            submitted_issue = st.form_submit_button("📤 送出回報")

        if submitted_issue:
            now = datetime.now()
            filename = ""
            if photo:
                extension = photo.name.split(".")[-1]
                filename = f"{now.strftime('%Y-%m-%d')}_{username}_{uuid.uuid4().hex[:6]}.{extension}"
                filepath = os.path.join(uploads_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(photo.getbuffer())
                st.image(photo, caption="已上傳的圖片", use_column_width=True)

            # 儲存紀錄
            new_issue = pd.DataFrame([{
                "username": username,
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "type": issue_type,
                "description": desc,
                "image_path": filepath if photo else ""
            }])

            try:
                issues_df = pd.read_csv(issue_logs_path)
                issues_df = pd.concat([issues_df, new_issue], ignore_index=True)
            except FileNotFoundError:
                issues_df = new_issue

            issues_df.to_csv(issue_logs_path, index=False)
            st.success("✅ 問題已送出，謝謝你回報！")

            # 發送 Telegram 通知
            
            TELEGRAM_BOT_TOKEN = st.secrets["TELE_BOT_TOKEN"]
            TELEGRAM_CHAT_ID = st.secrets["TELE_CHAT_ID"]

            msg = f"🚨 有新的問題回報\n👤 員工：{username}\n📅 日期：{now.strftime('%Y-%m-%d')}\n🕒 時間：{now.strftime('%H:%M')}\n📌 類型：{issue_type}\n📝 描述：{desc}"
            send_telegram_message(msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

        st.subheader("📖 我回報過的問題紀錄")

        try:
            issues_df = pd.read_csv("data/issue_logs.csv")
            issues_df = issues_df[issues_df["username"] == username].sort_values("date", ascending=False)

            for i, row in issues_df.iterrows():
                st.markdown(f"🗓️ **{row['date']}** - 🕒 {row['time']}")
                st.markdown(f"**類型**：{row['type']} | **狀態**：🟡 *{row['status']}*")
                st.markdown(f"**描述**：{row['description']}")
                if row["image_path"] and os.path.exists(row["image_path"]):
                    st.image(row["image_path"], width=300)
                st.markdown("---")
        except:
            st.info("尚無回報紀錄")


    # 管理員介面
    if role == "admin":
        st.subheader("📅 班表管理")

        with st.expander("查看本週班表"):
            sched = load_schedule()
            st.dataframe(sched)

        with st.expander("更新班表（上傳 CSV）"):
            upload = st.file_uploader("上傳新班表", type="csv")
            if upload:
                new_sched = pd.read_csv(upload)
                save_schedule(new_sched)
                st.success("班表已更新")

        with st.expander("查看打卡紀錄"):
            logs = pd.read_csv(LOG_PATH)
            st.dataframe(logs.tail(20))

        st.subheader("🛠️ 所有問題回報（管理員可更改狀態）")

        try:
            issues_df = pd.read_csv("data/issue_logs.csv")
            issues_df = issues_df.sort_values(["date", "time"], ascending=False)

            for i, row in issues_df.iterrows():
                st.markdown(f"🗓️ **{row['date']} {row['time']}** - 👤 {row['username']}")
                st.markdown(f"**類型**：{row['type']}")
                st.markdown(f"**描述**：{row['description']}")
                if row["image_path"] and os.path.exists(row["image_path"]):
                    st.image(row["image_path"], width=300)

                # 狀態選擇
                current_status = row.get("status", "未處理")
                new_status = st.selectbox(
                    f"更改狀態（問題編號 {i}）",
                    options=["未處理", "處理中", "已完成"],
                    index=["未處理", "處理中", "已完成"].index(current_status),
                    key=f"status_{i}"
                )

                # 更新狀態
                if new_status != current_status:
                    issues_df.at[i, "status"] = new_status
                    st.success(f"已更新為「{new_status}」")

                st.markdown("---")

            # 儲存更新
            issues_df.to_csv("data/issue_logs.csv", index=False)

        except FileNotFoundError:
            st.info("尚無回報資料")


else:
    st.warning("請輸入正確帳號與密碼登入")

TELEGRAM_BOT_TOKEN = "8000858451:AAHhU8v23NgsfR3t_zsYVjLjuXDmskm--c0"
TELEGRAM_CHAT_ID = "7321860394"  # 例：123456789

if st.button("測試發送 Telegram 通知"):
    test_msg = "這是一則測試訊息 ✅"
    send_telegram_message(test_msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)