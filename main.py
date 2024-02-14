import aiosqlite
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import F 
from bot_token import tg_token
from questions import quiz_data

# Включаем логгирование
logging.basicConfig(level= logging.INFO)
API_TOKEN = tg_token #вставьте свой токен в bot_token.py

# Объект класса бот
bot = Bot(token= API_TOKEN)

# Диспетчер
dp = Dispatcher()

# Имя для базы данных
DB_NAME = 'quiz_bot.db'

current_try = 0

# Хэндлер на /start
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text='Начать квиз'))
    builder.add(types.KeyboardButton(text= 'Моя статистика'))
    await message.answer('Привет! Я бот для проведения квиза. Введите /quiz или нажмите соответствующую кнопку, чтобы начать. Также вы можете просмотреть вашу статистику, нажав на соответствующую кнопку или введя /score', reply_markup= builder.as_markup(resize_keyboard= True))

def generate_options_keyboard(answer_options, right_answer):
    builder = InlineKeyboardBuilder()

    # Циклом создаем кнопки
    for option in answer_options:
        builder.add(types.InlineKeyboardButton(
            text= option,
            callback_data= f'right_answer/{option}' if option == right_answer else f'wrong_answer/{option}')  
        )

    # Выводим по одной кнопке в столбец
    builder.adjust(1)
    return builder.as_markup()

async def new_quiz(message):
    # Получаем id пользователя, отправившего сообщение
    user_id = message.from_user.id
    # Сброс индекса вопросов в 0
    current_question_index = 0
    # Сброс значения score - результат последнего теста
    current_score = 0
    global current_try
    current_try += 1
    await update_quiz_index(user_id, current_question_index, current_score, current_try)
    # Запрос нового вопроса
    await get_question(message, user_id)

async def get_question(message, user_id):
    # Запрос текущего индекса из БД
    current_question_index = await get_quiz_index(user_id)
    # Получаем индекс правильного ответа
    correct_index = quiz_data[current_question_index]['correct_option']
    # Получаем ваврианты ответа для текущего вопроса
    opts = quiz_data[current_question_index]['options']
    # Генерируем кнопки в вопрос
    kb = generate_options_keyboard(opts, opts[correct_index])
    await message.answer(f'{quiz_data[current_question_index]['question']}', reply_markup= kb)

async def save_score(user_id, score, user_try):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO quiz_score (user_id, score, user_try) VALUES (?, ?, ?)', (user_id, score, user_try))
        await db.commit()



async def show_score(message):
    result_score = []
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT user_try, score FROM quiz_score WHERE user_id = (?)', (user_id, )) as cursor:
            results = await cursor.fetchall()
            if results is not None:
                for i in range(len(results)):
                    result_score.append(results[i])
                return results
            else:
                return 'Вы еще не прошли ни одного теста'


# Хэндлер на /score
@dp.message(F.text== 'Моя статистика')
@dp.message(Command('score'))
async def cmd_score(message: types.Message):
    await message.answer('Ваша статистика прохождения тестов \n')
    score = await show_score(message)
    for row in score:
        await message.answer(f'{row[0]}. {row[1]} правильно') 

# Хэндлер на /quiz
@dp.message(F.text== 'Начать квиз') # Магический фильтр на точное значение текста
@dp.message(Command('quiz'))
async def cmd_quiz(message: types.Message):
    await message.answer('Начнем квиз!')
    await new_quiz(message)

# Функция для регистрации нового пользователя и "запоминания" вопроса
async def update_quiz_index(user_id, index, score, user_try):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index, score, user_try) VALUES (?, ?, ?, ?)', (user_id, index, score, user_try))
        await db.commit()

# Функция получения номера попытки
async def get_user_try(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT user_try FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

# Функция для извлечения текущего индекса вопроса
async def get_quiz_index(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0
            
# Функция для извлечения текущего результата
async def get_score(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT score FROM quiz_state WHERE user_id = (?)', (user_id, )) as cursor:
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0

# Обрабатываем правильные и неправильные ответы
@dp.callback_query(F.data.split('/')[0] == 'right_answer')
async def right_answer(callback: types.CallbackQuery):

    # Убираем кнопки
    await callback.bot.edit_message_reply_markup(
        chat_id= callback.from_user.id,
        message_id= callback.message.message_id,
        reply_markup= None    
    )

    await callback.bot.edit_message_text(
        chat_id= callback.from_user.id,
        message_id= callback.message.message_id,
        text= callback.message.text + '\n' + '\n' + callback.data.split('/')[1]
    )    

    # Получаем вопрос
    current_question_index = await get_quiz_index(callback.from_user.id)
    # Отвправляем в чат что ответ верный
    await callback.message.answer('Верно!')
    # Получаем результат
    current_score = await get_score(callback.from_user.id)
    # Обновляем результат
    current_score += 1
    # Обновляем номер вопроса в БД
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, current_score, current_try)
    # Проверка кончились ли вопросы
    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        await save_score(callback.from_user.id, current_score, current_try)
        await callback.message.answer('Это был последний вопрос')

@dp.callback_query(F.data.split('/')[0] == 'wrong_answer')
async def wrong_answer(callback: types.CallbackQuery):
    # Убираем кнопки
    await callback.bot.edit_message_reply_markup(
        chat_id= callback.from_user.id,
        message_id= callback.message.message_id,
        reply_markup= None    
    )

    await callback.bot.edit_message_text(
        chat_id= callback.from_user.id,
        message_id= callback.message.message_id,
        text= callback.message.text + '\n' + '\n' + callback.data.split('/')[1]
    )        

    # Получаем вопрос
    current_question_index = await get_quiz_index(callback.from_user.id)
    current_score = await get_score(callback.from_user.id)

    correct_option = quiz_data[current_question_index]['correct_option']

    # Пишем в чат что пользователь ошибся и правильный ответ
    await callback.message.answer(f'Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_option]}')

    # Обновляем номер вопроса в БД
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index, current_score, current_try)
    # Проверка кончились ли вопросы
    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        await save_score(callback.from_user.id, current_score, current_try)
        await callback.message.answer('Это был последний вопрос')

# Создаем таблицу в базе данных для "запоминания" ботом вопроса на котором остановился пользователь
async def create_table():
    # Соединение с базой данных (если она не существует, то будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # SQL-запрос к базе данных на языке mysql
        await db.execute('CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER, score INTEGER, user_try INTEGER)' )
        await db.execute('CREATE TABLE IF NOT EXISTS quiz_score (user_id INTEGER, score INTEGER, user_try INTEGER PRIMARY KEY)')
        # Коммит изменений
        await db.commit()

# Запуск поллинга новых апдейтов
async def main():
    # Создаем новую таблицу
    await create_table()

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())