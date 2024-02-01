import os
from uuid import uuid4
import discord
from dotenv import load_dotenv
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage, HumanMessage

from honcho import Client as HonchoClient

load_dotenv()


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

app_id = str(uuid4())

honcho = HonchoClient(app_id=app_id)

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


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = f"discord_{str(message.author.id)}"
    location_id=str(message.channel.id)

    sessions = honcho.get_sessions(user_id, location_id)
    if len(sessions) > 0:
        session = sessions[0]
    else:
        session = honcho.create_session(user_id, location_id)

    print(session)

    history = session.get_messages()
    chat_history = langchain_message_converter(history)

    inp = message.content
    session.create_message(is_user=True, content=inp)

    async with message.channel.typing():
        response = await chain.ainvoke({"chat_history": chat_history, "input": inp})
        await message.channel.send(response)

    session.create_message(is_user=False, content=response)

@bot.slash_command(name = "restart", description = "Restart the Conversation")
async def restart(ctx):
    user_id=f"discord_{str(ctx.author.id)}"
    location_id=str(ctx.channel_id)
    sessions = honcho.get_sessions(user_id, location_id)
    sessions[0].delete() if len(sessions) > 0 else None

    msg = "Great! The conversation has been restarted. What would you like to talk about?"
    await ctx.respond(msg)

bot.run(os.environ["BOT_TOKEN"])
