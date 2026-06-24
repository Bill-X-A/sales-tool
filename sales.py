import os
import json
import streamlit as st
from zhipuai import ZhipuAI
import base64
import pandas as pd
from datetime import datetime
import io

def save_record(data):
    # 先读取已有记录
    if os.path.exists("records.json"):
        with open("records.json", "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    
    # 追加新记录
    records.append(data)
    
    # 写回文件
    with open("records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)


client = ZhipuAI(api_key=st.secrets["ZHIPU_API_KEY"])

st.title("📋 销售录入助手")

uploaded_file = st.file_uploader("上传订单截图", type=["jpg", "jpeg", "png"])

member_levels = ["V0", "V1", "V2", "V3", "V4", "V5"]
member = st.selectbox("选择会员等级", member_levels, index=0)

if st.button("AI识别"):
    image_data = base64.b64encode(uploaded_file.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="glm-4v-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": """请从这张销售单截图中提取以下信息，以JSON格式返回：
    {
        "销售员": "",
        "备注后面的11位数字": "",
        "商品名称": "",
        "SN码": ""
    }
    只返回JSON，不要其他内容。"""
                    }
                ]
            }
        ]
    )

    # 解析JSON
    raw = response.choices[0].message.content
    clean = raw.strip().replace("```json", "").replace("```", "").strip()
    result = json.loads(clean)


    # 存入session_state，方便后面提交用
    st.session_state.销售员 = result.get("销售员", "")
    st.session_state.手机号 = result.get("备注后面的11位数字", "")
    st.session_state.商品名称 = result.get("商品名称", "")
    st.session_state.SN码 = result.get("SN码", "")

if "销售员" in st.session_state:
    st.session_state.销售员 = st.text_input("销售员", st.session_state.销售员)
    st.session_state.手机号 = st.text_input("手机号", st.session_state.手机号)
    st.session_state.商品名称 = st.text_input("商品名称", st.session_state.商品名称)
    st.session_state.SN码 = st.text_input("SN码", st.session_state.SN码)

if st.button("确认提交"):
    save_record({
        "销售员": st.session_state.销售员,
        "手机号": st.session_state.手机号,
        "商品名称": st.session_state.商品名称,
        "SN码": st.session_state.SN码,
        "会员等级": member,
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    st.success("提交成功！")

if st.button("查看历史记录"):
    if os.path.exists("records.json"):
        with open("records.json", "r", encoding="utf-8") as f:
            records = json.load(f)
        
        df = pd.DataFrame(records)
        st.dataframe(df)
        
        # 筛选今天的记录
        today = datetime.now().strftime("%Y-%m-%d")
        today_records = [r for r in records if r["时间"].startswith(today)]
        
        if today_records:
            df_today = pd.DataFrame(today_records)
            # 转成Excel
            buffer = io.BytesIO()
            df_today.to_excel(buffer, index=False)
            excel_data = buffer.getvalue()
            st.download_button(
                label="📥 下载今日记录",
                data=excel_data,
                file_name=f"销售记录_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("今天暂无记录")
    else:
        st.info("暂无历史记录")

