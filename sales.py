from datetime import datetime, timezone, timedelta
import os
import re
import json
import streamlit as st
from zhipuai import ZhipuAI
import base64
import pandas as pd
from datetime import datetime
import io
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from lark_oapi.api.drive.v1 import *
import requests
APP_ID = st.secrets["FEISHU_APP_ID"]
APP_SECRET = st.secrets["FEISHU_APP_SECRET"]
APP_TOKEN = "AO2NbKrqNaWFZ9suHKJcjGYLn4b"
TABLE_ID = "tbl1W59w24xZBvNc"

def save_to_feishu(data):
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .build()

    request = CreateAppTableRecordRequest.builder() \
        .app_token(APP_TOKEN) \
        .table_id(TABLE_ID) \
        .request_body(AppTableRecord.builder()
            .fields(data)
            .build()
        ) \
        .build()

    response = client.bitable.v1.app_table_record.create(request)
    return response.success()

def get_from_feishu():
    client = lark.Client.builder() \
        .app_id(APP_ID) \
        .app_secret(APP_SECRET) \
        .build()

    request = ListAppTableRecordRequest.builder() \
        .app_token(APP_TOKEN) \
        .table_id(TABLE_ID) \
        .build()

    response = client.bitable.v1.app_table_record.list(request)
    
    if response.success():
        records = []
        for item in response.data.items:
            records.append(item.fields)
        return records
    else:
        return []

def upload_image_to_feishu(image_bytes, filename):
    # 获取token
    token_res = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    ).json()
    token = token_res["tenant_access_token"]
    
    # 上传文件
    res = requests.post(
        "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "file_name": filename,
            "parent_type": "bitable_file",
            "parent_node": APP_TOKEN,
            "size": str(len(image_bytes))
        },
        files={"file": (filename, image_bytes, "image/jpeg")}
    ).json()
    
    if res.get("code") == 0:
        return res["data"]["file_token"]
    else:
        st.error(f"图片上传失败：{res}")
        return None

client = ZhipuAI(api_key=st.secrets["ZHIPU_API_KEY"])

st.title("📋 销售录入助手")

uploaded_file = st.file_uploader("上传订单截图", type=["jpg", "jpeg", "png"])

member_levels = ["V0", "V1", "V2", "V3", "V4", "V5"]
member = st.selectbox("选择会员等级", member_levels, index=0)

usage_options = ["国补", "自用拆封激活", "自用不激活", "送礼激活", "送礼不激活", "其他"]
usage = st.selectbox("购买用途", usage_options)

photo_file = st.file_uploader("上传三码合一照片", type=["jpg", "jpeg", "png"], key="photo")

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
        "备注后面的11位数字": "只提取【备注】这一行后面的11位数字，不要提取【手机号】字段的数字，如果备注里没有11位数字则返回13000000000"
        "商品名称": "",
        "SN码": "",
        "订单金额": "",
        "购买品类": ""
    }
                        购买品类判断规则：
                        - 商品名称包含"双卡" → "手机"
                        - 商品名称包含"MateBook" → "PC"
                        - 商品名称包含"MatePad" → "平板"
                        - 商品名称包含"手表"或"手环"或"WATCH" → "穿戴"
                        - 商品名称包含"耳机"或"Free" → "音频"
                        - 其他 → "配件"
                        只返回JSON，不要其他内容。"""
                    }
                ]
            }
        ]
    )

    # 解析JSON
    raw = response.choices[0].message.content
    clean = re.sub(r'```[\w]*', '', raw).strip()
    clean = ''.join(char for char in clean if ord(char) < 65536)
    clean = clean.replace('¥', '')
    result = json.loads(clean)
    st.session_state.销售员 = result.get("销售员", "")
    phone = result.get("备注后面的11位数字", "")
    if not (phone.isdigit() and len(phone) == 11):
    phone = "13000000000"
    st.session_state.手机号 = phone
    st.session_state.商品名称 = result.get("商品名称", "")
    st.session_state.SN码 = result.get("SN码", "")
    st.session_state.订单金额 = result.get("订单金额", "")
    st.session_state.购买品类 = result.get("购买品类", "")
    st.session_state.show_fields = True

if st.session_state.get("show_fields"):
    st.session_state.销售员 = st.text_input("销售员", st.session_state.销售员)
    st.session_state.手机号 = st.text_input("手机号", st.session_state.手机号)
    st.session_state.商品名称 = st.text_input("商品名称", st.session_state.商品名称)
    st.session_state.SN码 = st.text_input("SN码", st.session_state.SN码)
    st.session_state.订单金额 = st.text_input("订单金额", st.session_state.订单金额)
    st.session_state.购买品类 = st.text_input("购买品类", st.session_state.购买品类)

if st.button("确认提交"):
    # 先上传图片
    file_token = None
    if photo_file:
        file_token = upload_image_to_feishu(
            photo_file.read(),
            photo_file.name
        )
    
    # 准备提交数据
    data = {
        "标题": "销售记录",
        "销售员": st.session_state.销售员,
        "手机号": st.session_state.手机号,
        "商品名称": st.session_state.商品名称,
        "SN码": st.session_state.SN码,
        "订单金额": st.session_state.订单金额,
        "购买品类": st.session_state.购买品类,
        "购买用途": usage,
        "会员等级": member,
        "时间": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 如果有图片，加入附件字段
    if file_token:
        data["三码合一照片"] = [{"file_token": file_token}]
    
    success = save_to_feishu(data)
    if success:
        st.success("提交成功！")
    else:
        st.error("提交失败，请重试")

if st.button("查看历史记录"):
    records = get_from_feishu()
    if records:
        today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        today_records = [r for r in records if str(r.get("时间", "")).startswith(today)]
        if today_records:
            df = pd.DataFrame(today_records)
            st.dataframe(df)
        else:
            st.info("今天暂无记录")
    else:
        st.info("暂无历史记录")
        
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
