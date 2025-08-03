import asyncio
import random
import string
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = '7719533432:AAHhV3qYRgD3rZKKl7jYq54dFhMkN7I0mXE'
CRYPTOBOT_TOKEN = '435663:AArmdXRrs3UeZDzEiXcwZoSQP7clCkXdZTM'
ADMIN_ID = 5001689214

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

class BuyState(StatesGroup):
    choosing_amount = State()
    choosing_currency = State()

PRICES = {
    "bomj": {"usdt": 0.5, "ton": 0.15977258},
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
processed_invoices = set()

async def update_stock():
    while True:
        stock["bomj"] = random.randint(500, 1000)
        stock["random"] = random.randint(600, 1200)
        stock["fat"] = random.randint(100, 200)
        logger.info(f"Stock updated: {stock}")
        await asyncio.sleep(86400)

def generate_cookie():
    prefix = "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_CAEaAhAB."
    data = ''.join(random.choices(string.ascii_letters + string.digits, k=700))
    return prefix + data

def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Товары", callback_data="show_products")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")],
        [InlineKeyboardButton(text="📞 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instructions")]
    ])
    return kb

def product_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Бомж куки ({stock['bomj']} шт) - {PRICES['bomj']['usdt']} USDT / {PRICES['bomj']['ton']} TON", callback_data="buy_bomj")],
        [InlineKeyboardButton(text=f"Рандом куки ({stock['random']} шт) - {PRICES['random']['usdt']} USDT / {PRICES['random']['ton']} TON", callback_data="buy_random")],
        [InlineKeyboardButton(text=f"Жир куки ({stock['fat']} шт) - {PRICES['fat']['usdt']} USDT / {PRICES['fat']['ton']} TON", callback_data="buy_fat")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return kb

def currency_menu(item):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USDT", callback_data=f"currency_usdt_{item}")],
        [InlineKeyboardButton(text="💎 TON", callback_data=f"currency_ton_{item}")]
    ])
    return kb

async def send_cookie_files(user_id: int, inv_payload: str, item: str, amount: int):
    stock[item] -= amount
    for i in range(amount):
        cookie = generate_cookie()
        file_name = f"cookie_{inv_payload}_{i}.txt"
        with open(file_name, "w") as f:
            f.write(cookie)
        try:
            await bot.send_document(user_id, FSInputFile(file_name))
            logger.info(f"Sent cookie file {file_name} to user {user_id}")
        finally:
            try:
                os.remove(file_name)
                logger.info(f"Deleted cookie file {file_name}")
            except Exception as e:
                logger.error(f"Failed to delete cookie file {file_name}: {str(e)}")
    await bot.send_message(user_id, "Оплата подтверждена! Товар отправлен.")

async def check_payments_task():
    retry_count = 0
    max_retries = 3
    while True:
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
            try:
                async with session.get("https://pay.crypt.bot/api/getInvoices", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    raw_response = await resp.text()
                    logger.info(f"Raw payment check response: {raw_response}")
                    resp_data = await resp.json()
                    logger.info(f"Payment check API response: {resp_data}")
                    if not isinstance(resp_data, dict):
                        logger.error(f"Invalid API response type: expected dict, got {type(resp_data)}")
                        await asyncio.sleep(10)
                        continue
                    if resp_data.get("ok"):
                        result = resp_data.get("result")
                        if isinstance(result, dict):
                            logger.info("Result is a single dictionary, converting to list")
                            result = [result]
                        elif not isinstance(result, (list, dict)):
                            logger.error(f"Invalid result type: expected list or dict, got {type(result)}")
                            await asyncio.sleep(10)
                            continue
                        for invoice in result if isinstance(result, list) else [result]:
                            if not isinstance(invoice, dict):
                                logger.error(f"Invalid invoice type: expected dict, got {type(invoice)}")
                                continue
                            inv_payload = invoice.get("payload")
                            status = invoice.get("status")
                            if not inv_payload or not status:
                                logger.error(f"Missing payload or status in invoice: {invoice}")
                                continue
                            logger.info(f"Checking invoice: payload={inv_payload}, status={status}")
                            if (status == "paid" and 
                                inv_payload not in processed_invoices and 
                                inv_payload in user_data):
                                user_id = user_data[inv_payload]["user_id"]
                                item = user_data[inv_payload]["item"]
                                amount = user_data[inv_payload]["amount"]
                                processed_invoices.add(inv_payload)
                                await send_cookie_files(user_id, inv_payload, item, amount)
                                del user_data[inv_payload]
                                logger.info(f"Processed invoice {inv_payload} for user {user_id}")
                    else:
                        error_message = resp_data.get("error", "Неизвестная ошибка")
                        logger.error(f"Failed to check invoices: {error_message}")
            except Exception as e:
                retry_count += 1
                logger.error(f"Exception during payment check (attempt {retry_count}/{max_retries}): {str(e)}")
                if retry_count < max_retries:
                    await asyncio.sleep(5 * retry_count)
                    continue
                retry_count = 0
            await asyncio.sleep(10)

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать в <b>ChiterShop</b>! 🎉\n"
        "Выберите действие в меню ниже:",
        reply_markup=main_menu()
    )

@router.callback_query(lambda c: c.data == "show_products")
async def show_products(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>Доступные товары</b>:\n\n"
        "Выберите товар для покупки:",
        reply_markup=product_menu()
    )

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Добро пожаловать в <b>ChiterShop</b>! 🎉\n"
        "Выберите действие в меню ниже:",
        reply_markup=main_menu()
    )

@router.callback_query(lambda c: c.data == "info")
async def show_info(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>Информация о магазине</b>\n\n"
        "ChiterShop - ваш надёжный магазин куки! 🍪\n"
        "Мы предлагаем качественные товары по доступным ценам.\n"
        "Оплата через CryptoBot в USDT или TON.\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

@router.callback_query(lambda c: c.data == "support")
async def show_support(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📞 <b>Поддержка</b>\n\n"
        "Если у вас есть вопросы или проблемы, свяжитесь с нами: @p2pica\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

@router.callback_query(lambda c: c.data == "instructions")
async def send_instructions(callback: types.CallbackQuery):
    instructions_url = "https://docs.google.com/document/d/1wKRnzBFxOAVaUqJmz-AIjEE9P3FRgvZsJn7jGVwfzkE/edit?usp=sharing"
    try:
        await callback.message.edit_text(
            "📖 <b>Инструкция</b>\n\n"
            "Ознакомьтесь с инструкцией по использованию куки по ссылке ниже:\n"
            f'<a href="{instructions_url}">Инструкция</a>',
            reply_markup=main_menu()
        )
        logger.info(f"Sent instructions link to user {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Error sending instructions link to user {callback.from_user.id}: {str(e)}")
        await callback.message.edit_text(
            "Ошибка при отправке инструкции. Обратитесь в поддержку: @ChiterShopSupport.",
            reply_markup=main_menu()
        )

@router.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def ask_amount(callback: types.CallbackQuery, state: FSMContext):
    item = callback.data.split('_')[1]
    await state.update_data(item=item)
    await callback.message.edit_text(
        f"Вы выбрали <b>{item_names[item]}</b>.\n"
        f"Цена: {PRICES[item]['usdt']} USDT / {PRICES[item]['ton']} TON за штуку.\n\n"
        "Выберите валюту для оплаты:",
        reply_markup=currency_menu(item)
    )
    await state.set_state(BuyState.choosing_currency)

@router.callback_query(lambda c: c.data and c.data.startswith("currency_"))
async def process_currency(callback: types.CallbackQuery, state: FSMContext):
    currency, item = callback.data.split('_')[1:]
    await state.update_data(currency=currency)
    await callback.message.edit_text(
        f"Вы выбрали <b>{item_names[item]}</b>.\n"
        f"Валюта: <b>{currency.upper()}</b>.\n\n"
        f"Введите количество, которое хотите купить:"
    )
    await state.set_state(BuyState.choosing_amount)

@router.message(BuyState.choosing_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError("Количество должно быть больше нуля.")
    except ValueError as e:
        await message.answer(f"Ошибка: {str(e) or 'Введите корректное количество.'}")
        return

    data = await state.get_data()
    item = data['item']
    currency = data['currency']

    if amount > stock[item]:
        await message.answer(f"Ошибка: На складе только {stock[item]} шт. {item_names[item]}.")
        return

    total = round(PRICES[item][currency] * amount, 6)
    payload = f"{message.from_user.id}_{item}_{amount}"

    user_data[payload] = {
        "item": item,
        "amount": amount,
        "currency": currency,
        "user_id": message.from_user.id
    }
    logger.info(f"Added to user_data: {payload} -> {user_data[payload]}")

    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
        }
        invoice_data = {
            "asset": currency.upper(),
            "amount": total,
            "description": f"Покупка: {item_names[item]} x{amount}",
            "hidden_message": "Куки будут отправлены автоматически после успешной оплаты.",
            "payload": payload,
            "paid_btn_name": "viewItem",
            "paid_btn_url": "https://t.me/chitershop_bot"
        }
        try:
            async with session.post("https://pay.crypt.bot/api/createInvoice", json=invoice_data, headers=headers) as resp:
                resp_data = await resp.json()
                logger.info(f"CryptoBot invoice creation response: {resp_data}")
                if resp_data.get("ok"):
                    pay_url = resp_data["result"]["pay_url"]
                    await message.answer(
                        f"Вы выбрали: <b>{item_names[item]}</b>\n"
                        f"Количество: <b>{amount}</b>\n"
                        f"💰 Сумма к оплате: <b>{total} {currency.upper()}</b>\n\n"
                        f"Нажмите кнопку ниже для перехода к оплате. Товар будет отправлен автоматически после оплаты.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text=f"💳 Оплатить через CryptoBot ({currency.upper()})", url=pay_url)],
                            [InlineKeyboardButton(text="🔙 Назад", callback_data="show_products")]
                        ])
                    )
                else:
                    error_message = resp_data.get("error", "Неизвестная ошибка")
                    logger.error(f"Failed to create invoice: {error_message}")
                    await message.answer(f"Ошибка при создании счёта: {error_message}. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Exception during invoice creation: {str(e)}")
            await message.answer("Ошибка при создании счёта. Проверьте подключение и попробуйте позже.")
    await state.clear()

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"<b>Текущее наличие:</b>\n\n"
            f"Бомж куки: {stock['bomj']}\n"
            f"Рандом куки: {stock['random']}\n"
            f"Жир куки: {stock['fat']}",
            reply_markup=main_menu()
        )
    else:
        await message.answer("У вас нет доступа к админ панели.")

@router.message(Command("check"))
async def check_payment(message: types.Message):
    payload = f"{message.from_user.id}_"
    async with aiohttp.ClientSession() as session:
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        try:
            async with session.get("https://pay.crypt.bot/api/getInvoices", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                raw_response = await resp.text()
                logger.info(f"Raw manual check response: {raw_response}")
                resp_data = await resp.json()
                logger.info(f"Manual check payment API response: {resp_data}")
                if not isinstance(resp_data, dict):
                    logger.error(f"Invalid API response type: expected dict, got {type(resp_data)}")
                    await message.answer(
                        "Ошибка при проверке оплаты: неверный формат ответа API.\n"
                        "Платежи обрабатываются автоматически каждые 10 секунд. Попробуйте снова через 2-3 минуты.\n"
                        "Если проблема сохраняется, свяжитесь с поддержкой: @ChiterShopSupport."
                    )
                    return
                if resp_data.get("ok"):
                    result = resp_data.get("result")
                    if isinstance(result, dict):
                        logger.info("Manual check: Result is a single dictionary, converting to list")
                        result = [result]
                    elif not isinstance(result, (list, dict)):
                        logger.error(f"Invalid result type: expected list or dict, got {type(result)}")
                        await message.answer(
                            "Ошибка при проверке оплаты: неверный формат данных.\n"
                            "Платежи обрабатываются автоматически каждые 10 секунд. Попробуйте снова через 2-3 минуты.\n"
                            "Если проблема сохраняется, свяжитесь с поддержкой: @ChiterShopSupport."
                        )
                        return
                    for invoice in result if isinstance(result, list) else [result]:
                        if not isinstance(invoice, dict):
                            logger.error(f"Invalid invoice type: expected dict, got {type(invoice)}")
                            continue
                        inv_payload = invoice.get("payload")
                        status = invoice.get("status")
                        if not inv_payload or not status:
                            logger.error(f"Missing payload or status in invoice: {invoice}")
                            continue
                        logger.info(f"Manual check: Checking invoice: payload={inv_payload}, status={status}")
                        if (status == "paid" and 
                            inv_payload not in processed_invoices and 
                            inv_payload in user_data):
                            user_id = user_data[inv_payload]["user_id"]
                            item = user_data[inv_payload]["item"]
                            amount = user_data[inv_payload]["amount"]
                            processed_invoices.add(inv_payload)
                            await send_cookie_files(user_id, inv_payload, item, amount)
                            del user_data[inv_payload]
                            logger.info(f"Manually processed invoice {inv_payload} for user {user_id}")
                            return
                    await message.answer(
                        "Оплата не найдена. Убедитесь, что вы оплатили счёт через CryptoBot.\n"
                        "Платежи обрабатываются автоматически каждые 10 секунд, но могут занять 2-3 минуты.\n"
                        "Если товар не получен, свяжитесь с поддержкой: @ChiterShopSupport."
                    )
                else:
                    error_message = resp_data.get("error", "Неизвестная ошибка")
                    logger.error(f"Failed to check invoices: {error_message}")
                    await message.answer(
                        f"Ошибка при проверке оплаты: {error_message}.\n"
                        "Попробуйте снова через несколько минут или свяжитесь с поддержкой: @ChiterShopSupport."
                    )
        except Exception as e:
            logger.error(f"Exception during manual payment check: {str(e)}")
            await message.answer(
                "Ошибка при проверке оплаты: проблема с подключением или API.\n"
                "Платежи обрабатываются автоматически каждые 10 секунд. Попробуйте снова через 2-3 минуты.\n"
                "Если проблема сохраняется, свяжитесь с поддержкой: @ChiterShopSupport."
            )

async def main():
    dp.include_router(router)
    asyncio.create_task(update_stock())
    asyncio.create_task(check_payments_task())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
