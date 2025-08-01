import asyncio
import random
import string
import os
import time
import threading
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram import Router
from aiocryptopay import AioCryptoPay, Networks

API_TOKEN = os.getenv("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_URL = "https://chitershop.onrender.com/webhook"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
app = Flask(__name__)
crypto = AioCryptoPay(token=CRYPTOBOT_TOKEN, network=Networks.MAIN_NET)

class BuyState(StatesGroup):
    choosing_amount = State()

PRICES = {
    "bomj": {"usdt": 0.5, "ton": 0.00977258},
    "random": {"usdt": 1.0, "ton": 0.32017184},
    "fat": {"usdt": 2.5, "ton": 0.79812681}
}

stock = {
    "bomj": 0,
    "random": 0,
    "fat": 0
}

item_names = {
    "bomj": "Бомж куки",
    "random": "Рандом куки",
    "fat": "Жир куки"
}

user_data = {}

async def update_stock():
    while True:
        stock["bomj"] = random.randint(500, 1000)
        stock["random"] = random.randint(600, 1200)
        stock["fat"] = random.randint(100, 200)
        await asyncio.sleep(86400)

def generate_cookie():
    prefix = "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|"
    data = ''.join(random.choices(string.ascii_letters + string.digits, k=700))
    return prefix + data

def product_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Бомж куки ({stock['bomj']} шт)", callback_data="buy_bomj")],
        [InlineKeyboardButton(text=f"Рандом куки ({stock['random']} шт)", callback_data="buy_random")],
        [InlineKeyboardButton(text=f"Жир куки ({stock['fat']} шт)", callback_data="buy_fat")]
    ])

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать в <b>ChiterShop</b>!\nВыберите товар:", reply_markup=product_keyboard())

@router.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def ask_amount(callback: types.CallbackQuery, state: FSMContext):
    item = callback.data.split('_')[1]
    await state.update_data(item=item)
    await callback.message.answer(f"Вы выбрали <b>{item_names[item]}</b>.\nВведите количество, которое хотите купить:")
    await state.set_state(BuyState.choosing_amount)

@router.message(BuyState.choosing_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное количество.")
        return

    data = await state.get_data()
    item = data['item']
    total_ton = round(PRICES[item]['ton'] * amount, 6)
    payload = f"{message.from_user.id}_{item}_{amount}"

    user_data[payload] = {
        "item": item,
        "amount": amount,
        "user_id": message.from_user.id
    }

    invoice = await crypto.create_invoice(
        asset="TON",
        amount=total_ton,
        description=f"Покупка: {item_names[item]} x{amount}",
        hidden_message="Куки будут отправлены после успешной оплаты.",
        payload=payload,
        paid_btn_name="viewItem",
        paid_btn_url="https://t.me/chitershop_bot"
    )

    await message.answer(
        f"Вы выбрали: <b>{item_names[item]}</b>\n"
        f"Количество: <b>{amount}</b>\n"
        f"💰 Сумма к оплате: <b>{total_ton} TON</b>\n\n"
        f"Нажмите кнопку ниже для перехода к оплате:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=invoice.pay_url)]
        ])
    )

    await state.clear()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return "no data", 400

    if data.get("update_type") == "invoice_paid":
        payload = data.get("payload")
        print("[PAYMENT CONFIRMED]", payload)

        if payload in user_data:
            item = user_data[payload]["item"]
            amount = user_data[payload]["amount"]
            user_id = user_data[payload]["user_id"]

            async def send():
                try:
                    for i in range(amount):
                        cookie = generate_cookie()
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🍪 <b>Ваш cookie #{i+1}:</b>\n<code>{cookie}</code>",
                            parse_mode=ParseMode.HTML
                        )
                    del user_data[payload]
                except Exception as e:
                    print("[ERROR SENDING COOKIE]", e)

            asyncio.run_coroutine_threadsafe(send(), asyncio.get_event_loop())

    return "ok", 200

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"<b>Текущее наличие:</b>\n\n"
            f"Бомж куки: {stock['bomj']}\n"
            f"Рандом куки: {stock['random']}\n"
            f"Жир куки: {stock['fat']}"
        )
    else:
        await message.answer("У вас нет доступа к админ панели.")

async def set_webhook():
    await crypto.set_webhook(WEBHOOK_URL)

async def main():
    dp.include_router(router)
    asyncio.create_task(update_stock())
    await set_webhook()
    # await dp.start_polling(bot)

if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8000)).start()
    asyncio.run(main())
