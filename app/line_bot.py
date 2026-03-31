import os
import re
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from app.providers.histock_provider import HiStockProvider, HiStockProviderError
from app.watchlist_db import add_watchlist, list_watchlist, remove_watchlist

load_dotenv()

router = APIRouter()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET or not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_SECRET or LINE_CHANNEL_ACCESS_TOKEN is not set")

handler = WebhookHandler(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
provider = HiStockProvider()


@router.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    body_text = body.decode("utf-8")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return {"status": "ok"}


def _extract_user_id(event: MessageEvent) -> str:
    source = event.source
    user_id = getattr(source, "user_id", None)
    return user_id or "unknown_user"


def _help_text() -> str:
    return (
        "可用指令：\n"
        "1. 直接輸入股票代號，例如：2330\n"
        "2. trend 2330\n"
        "3. 趨勢 2330\n"
        "4. 加入 2330\n"
        "5. 刪除 2330\n"
        "6. 我的自選\n"
        "7. 說明"
    )

def parse_command(text: str) -> tuple[str, str | None]:
    raw = text.strip()
    lower_raw = raw.lower()

    if not raw:
        return ("empty", None)

    # 純數字：直接查最新摘要
    if raw.isdigit():
        return ("summary", raw)

    # 我的自選 / 說明 / 查股票 / 新增自選
    if raw in {"我的自選"}:
        return ("watchlist", None)

    if raw in {"說明", "help", "幫助", "?"}:
        return ("help", None)

    if raw in {"查股票"}:
        return ("prompt_stock", None)

    if raw in {"新增自選"}:
        return ("prompt_add", None)

    # trend2330 / trend 2330 / 趨勢2330 / 趨勢 2330
    m = re.fullmatch(r"(?:trend|趨勢)\s*(\d+)", lower_raw)
    if m:
        return ("trend", m.group(1))

    # 加入2330 / 加入 2330
    m = re.fullmatch(r"加入\s*(\d+)", raw)
    if m:
        return ("add", m.group(1))

    # 刪除2330 / 刪除 2330
    m = re.fullmatch(r"刪除\s*(\d+)", raw)
    if m:
        return ("remove", m.group(1))

    return ("unknown", None)
def build_reply_text(user_text: str, line_user_id: str) -> str:
    action, stock_id = parse_command(user_text)

    if action == "empty":
        return "請輸入股票代號，例如 2330"

    if action == "help":
        return _help_text()

    if action == "prompt_stock":
        return "請直接輸入股票代號，例如 2330"

    if action == "prompt_add":
        return "請輸入：加入2330"

    if action == "watchlist":
        stocks = list_watchlist(line_user_id)
        if not stocks:
            return "你的自選股清單目前是空的。"

        joined = "\n".join(f"{idx + 1}. {sid}" for idx, sid in enumerate(stocks))
        return f"你的自選股：\n{joined}"

    if action == "add":
        inserted = add_watchlist(line_user_id, stock_id)
        if inserted:
            return f"已加入自選：{stock_id}"
        return f"{stock_id} 已經在你的自選股清單中"

    if action == "remove":
        deleted = remove_watchlist(line_user_id, stock_id)
        if deleted:
            return f"已刪除自選：{stock_id}"
        return f"你的自選股清單中沒有 {stock_id}"

    if action == "trend":
        try:
            return provider.summarize_six_month_trend(stock_id)
        except HiStockProviderError as exc:
            return f"查詢失敗：{exc}"
        except Exception as exc:
            return f"系統錯誤：{exc}"

    if action == "summary":
        try:
            return provider.summarize_latest_two_dates(stock_id)
        except HiStockProviderError as exc:
            return f"查詢失敗：{exc}"
        except Exception as exc:
            return f"系統錯誤：{exc}"

    return _help_text()

def build_quick_reply(user_text: str) -> QuickReply | None:
    text = user_text.strip()
    lower_text = text.lower()

    # 只有在「直接查股票」時顯示這組按鈕
    if text.isdigit():
        return QuickReply(
            items=[
                QuickReplyItem(
                    action=MessageAction(label="📈 趨勢", text=f"trend {text}")
                ),
                QuickReplyItem(
                    action=MessageAction(label="⭐ 加入自選", text=f"加入 {text}")
                ),
                QuickReplyItem(
                    action=MessageAction(label="📋 我的自選", text="我的自選")
                ),
            ]
        )

    # 查完趨勢時，也給常用按鈕
    if lower_text.startswith("trend ") or text.startswith("趨勢 "):
        parts = text.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            stock_id = parts[-1]
            return QuickReply(
                items=[
                    QuickReplyItem(
                        action=MessageAction(label="📊 最新摘要", text=stock_id)
                    ),
                    QuickReplyItem(
                        action=MessageAction(label="⭐ 加入自選", text=f"加入 {stock_id}")
                    ),
                    QuickReplyItem(
                        action=MessageAction(label="📋 我的自選", text="我的自選")
                    ),
                ]
            )

    # 看自選時，給常用入口
    if text == "我的自選":
        return QuickReply(
            items=[
                QuickReplyItem(
                    action=MessageAction(label="➕ 新增自選", text="加入 2330")
                ),
                QuickReplyItem(
                    action=MessageAction(label="❓ 使用說明", text="說明")
                ),
            ]
        )

    return None
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_text = event.message.text
    line_user_id = _extract_user_id(event)
    reply_text = build_reply_text(user_text, line_user_id)
    quick_reply = build_quick_reply(user_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(
                        text=reply_text,
                        quick_reply=quick_reply,
                    )
                ],
            )
        )