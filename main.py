import asyncio
import random
import string
import aiohttp
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiohttp import web

API_TOKEN = os.getenv('API_TOKEN')
CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
ADMIN_ID = 5001689214

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Бомж куки ({stock['bomj']} шт)", callback_data="buy_bomj")],
        [InlineKeyboardButton(text=f"Рандом куки ({stock['random']} шт)", callback_data="buy_random")],
        [InlineKeyboardButton(text=f"Жир куки ({stock['fat']} шт)", callback_data="buy_fat")]
    ])
    return kb

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать в <b>ChiterShop</b>!\nВыберите товар:", reply_markup=product_keyboard())

@router.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def ask_amount(callback: types.CallbackQuery, state: FSMContext):
    item = callback.data.split('_')[1]
    if stock[item] <= 0:
        await callback.message.answer(f"Товара <b>{item_names[item]}</b> нет в наличии!")
        return
    await state.update_data(item=item)
    await callback.message.answer(f"Вы выбрали <b>{item_names[item]}</b>.\nВведите количество, которое хотите купить:")
    await state.set_state(BuyState.choosing_amount)

@router.message(BuyState.choosing_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
        data = await state.get_data()
        item = data['item']
        if amount > stock[item]:
            await message.answer(f"Недостаточно товара <b>{item_names[item]}</b> в наличии! Остаток: {stock[item]} шт.")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите корректное количество.")
        return

    total_ton = round(PRICES[item]['ton'] * amount, 6)
    payload = f"{message.from_user.id}_{item}_{amount}"

    user_data[payload] = {
        "item": item,
        "amount": amount,
        "user_id": message.from_user.id
    }

    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
        }
        invoice_data = {
            "asset": "TON",
            "amount": total_ton,
            "description": f"Покупка: {item_names[item]} x{amount}",
            "hidden_message": "Куки будут отправлены после успешной оплаты.",
            "payload": payload,
            "paid_btn_name": "viewItem",
            "paid_btn_url": "https://t.me/chitershop_bot"
        }
        async with session.post("https://pay.crypt.bot/api/createInvoice", json=invoice_data, headers=headers) as resp:
            resp_data = await resp.json()
            if resp_data.get("ok"):
                pay_url = resp_data["result"]["pay_url"]
                await message.answer(
                    f"Вы выбрали: <b>{item_names[item]}</b>\n"
                    f"Количество: <b>{amount}</b>\n"
                    f"💰 Сумма к оплате: <b>{total_ton} TON</b>\n\n"
                    f"Нажмите кнопку ниже для перехода к оплате:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=pay_url)]
                    ])
                )
            else:
                await message.answer("Ошибка при создании счёта. Попробуйте позже.")
    await state.clear()

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

async def handle_webhook(request):
    data = await request.json()
    if data.get("update_type") == "invoice_paid":
        payload = data["payload"]
        if payload in user_data:
            item = user_data[payload]["item"]
            amount = user_data[payload]["amount"]
            user_id = user_data[payload]["user_id"]
            stock[item] -= amount  # Зменшуємо запаси
            for i in range(amount):
                cookie = generate_cookie()
                filename = f"cookie_{user_id}_{i}.txt"
                with open(filename, "w") as f:
                    f.write(cookie)
                await bot.send_document(user_id, FSInputFile(filename))
                os.remove(filename)  # Видаляємо файл після відправки
            del user_data[payload]
            await bot.send_message(user_id, f"Спасибо за покупку! Вы получили {amount} {item_names[item]}.")
    return web.Response()

async def start_webhook_server():
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Порт 8080 для Render
    await site.start()

async def main():
    dp.include_router(router)
    asyncio.create_task(update_stock())
    async with aiohttp.ClientSession() as session:
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        async with session.post(
            "https://pay.crypt.bot/api/setWebhook",
            json={"url": WEBHOOK_URL},
            headers=headers
        ) as resp:
            print(await resp.json())
    asyncio.create_task(start_webhook_server())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
