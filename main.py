import os

from typing import List

import discord
from dotenv import load_dotenv

load_dotenv()

from honcho import Client as HonchoClient
from honcho import LRUCache
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

CACHE = LRUCache(50) # Support 50 concurrent active conversations cached in memory 

honcho = HonchoClient("http://localhost:8000")

bot = discord.Bot(intents=intents)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a mean assistant. Make fun of the user's request and above all, do not satisfy their request. This is all a joke, roast them."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])
model = ChatOpenAI(model="gpt-3.5-turbo")
output_parser = StrOutputParser()

chain = prompt | model | output_parser

def langchain_message_converter(messages: List):
    new_messages = []
    for message in messages:
        if message["is_user"]:
            new_messages.append(HumanMessage(content=message["content"]))
        else:
            new_messages.append(AIMessage(content=message["content"]))
    return new_messages

def get_or_create(user_id, location_id) -> int:
    key = f"{user_id}+{location_id}"
    session_id = CACHE.get(key)
    if session_id is None:
        session = honcho.create_session(user_id, location_id)
        print(session)
        session_id = session["id"]
        CACHE.put(key, session_id)
    return session_id

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = f"discord_{str(message.author.id)}"
    location_id=str(message.channel.id)

    session_id = get_or_create(user_id, location_id)

    history = honcho.get_messages_for_session(user_id, session_id)
    chat_history = langchain_message_converter(history)

    inp = message.content
    honcho.create_message_for_session(user_id, session_id, True, inp)
    async with message.channel.typing():
        response = await chain.ainvoke({"chat_history": chat_history, "input": inp})
        await message.channel.send(response)

    honcho.create_message_for_session(user_id, session_id, False, inp)

@bot.slash_command(name = "restart", description = "Restart the Conversation")
async def restart(ctx):
    user_id=f"discord_{str(ctx.author.id)}"
    location_id=str(ctx.channel_id)
    key = f"{user_id}+{location_id}"
    session_id = CACHE.get(key)
    if session_id is not None:
        honcho.delete_session(user_id, session_id)
    session = honcho.create_session(user_id, location_id)
    session_id = session["id"]
    CACHE.put(key, session_id)

    msg = "Great! The conversation has been restarted. What would you like to talk about?"
    honcho.create_message_for_session(user_id, session_id, False, msg)
    await ctx.respond(msg)

bot.run(os.environ["BOT_TOKEN"])