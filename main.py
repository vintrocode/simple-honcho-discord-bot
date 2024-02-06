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

app_id = str("roast-bot")

honcho = HonchoClient(base_url="http://localhost:8000", app_id=app_id)

bot = discord.Bot(intents=intents)

response_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a mean assistant. Make fun of the user's request and above all, do not satisfy their request. This is all a joke, roast them.\n{thought}"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])
thought_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are tasked with using your theory of mind skills to make a comment about the user's mental state. The goal is to identify some insecurity the user might have. This is all to aid roasting the user for comedic purposes."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}")
])

model = ChatOpenAI(model="gpt-4")
output_parser = StrOutputParser()

response_chain = response_prompt | model | output_parser
thought_chain = thought_prompt | model | output_parser


async def thought(chat_history: List, input: str) -> str:
    response = await thought_chain.ainvoke({"chat_history": chat_history, "input": input})
    return response

def langchain_message_converter(messages: List):
    new_messages = []
    for message in messages:
        if message.is_user:
            new_messages.append(HumanMessage(content=message.content))
        else:
            new_messages.append(AIMessage(content=message.content))
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
    print(sessions)
    if len(sessions) > 0:
        session = sessions[0]
    else:
        session = honcho.create_session(user_id, location_id)

    history = session.get_messages()
    chat_history = langchain_message_converter(history)

    inp = message.content
    session.create_message(is_user=True, content=inp)

    async with message.channel.typing():
        thought = await thought_chain.ainvoke({"chat_history": chat_history, "input": inp})
        print(f"THOUGHT: {thought}")
        response = await response_chain.ainvoke({"thought": thought, "chat_history": chat_history, "input": inp})
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
