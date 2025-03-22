import os
import discord
from discord.ext import commands


from ollama import chat
from ollama import ChatResponse
from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path('D:\Projects\AILLMModels\DiscordOllamaBot\.env')
load_dotenv(dotenv_path=dotenv_path)

intents =  discord.Intents.default()
intents.message_content = True

bot =  commands.Bot(command_prefix="/", intents=intents)

# Dictionary to store conversation history per user
conversation_history = {}


@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user.name}')

@bot.command(name="hello")
async def hello(ctx):
        await ctx.send("Hello, I'm a bot!")


@bot.command(name="ask")
async def ask(ctx, *, message):
    user_id = ctx.author.id  # Unique identifier for each user

    # Retrieve conversation history or start a new one
    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {
                'role': 'system',
                'content': 'You are a helpful assistant who remembers past messages in the conversation.',
            }
        ]

    # Append the new user message to history
    conversation_history[user_id].append({'role': 'user', 'content': message})

    # Call Ollama with the updated conversation history
    response = chat(model='hermes3:8b', messages=conversation_history[user_id])

    # Add bot response to history
    bot_response = response['message']['content']
    conversation_history[user_id].append({'role': 'assistant', 'content': bot_response})

    # Limit history size (e.g., last 10 messages to prevent overload)
    conversation_history[user_id] = conversation_history[user_id][-10:]

    # Send response in chunks if necessary
    for chunk in [bot_response[i:i+2000] for i in range(0, len(bot_response), 2000)]:
        await ctx.send(chunk)

@bot.command(name="clear")
async def clear(ctx):
    """Clears conversation history for the user."""
    user_id = ctx.author.id
    if user_id in conversation_history:
        del conversation_history[user_id]
        await ctx.send("Conversation history cleared.")
    else:
        await ctx.send("No conversation history found.")


bot.run(os.getenv('DISCORD_BOT_TOKEN'))


    
print(response.message.content)
