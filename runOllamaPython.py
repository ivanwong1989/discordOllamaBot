import os
import discord
import aiohttp
from discord.ext import commands
from bs4 import BeautifulSoup


from ollama import chat
from ollama import ChatResponse
from dotenv import load_dotenv
from pathlib import Path

# Load ENV
load_dotenv()

# Discord bot intents
intents =  discord.Intents.default()
intents.message_content = True

bot =  commands.Bot(command_prefix="/", intents=intents)

# Dictionary to store conversation history per user
MAX_HISTORY = 10  # Set the max number of messages to store per user
conversation_history = {}


# Google Search Function
async def google_search(query):
    """Fetches top web search results and extracts content for summarization."""
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    search_url = "https://www.googleapis.com/customsearch/v1"

    params = {"q": query, "key": api_key, "cx": cx, "num": 5}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as response:
                if response.status != 200:
                    return f"Error: Unable to fetch search results (HTTP {response.status})"
                data = await response.json()

        if "items" not in data:
            return "No relevant search results found."

        search_results = []
        for item in data["items"][:3]:
            content = await fetch_page_content(item["link"])
            search_results.append(f"Title: {item['title']}\nSnippet: {item['snippet']}\nContent: {content}\nURL: {item['link']}")

        return "\n\n".join(search_results)

    except Exception as e:
        return f"An error occurred while searching: {str(e)}"

# Fetch page content from Google Search
async def fetch_page_content(url):
    """Fetches and extracts main content from a webpage."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return "Content not accessible."
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        paragraphs = soup.find_all("p")
        content = " ".join([p.get_text() for p in paragraphs[:5]])  # Limit to first 5 paragraphs
        return content if content else "No readable content found."

    except Exception:
        return "Error extracting content."

# Use LLM to summarize search results
async def summarize_text(text):
    """Summarizes a given text using Ollama."""
    try:
        response = chat(model='hermes3:3b', messages=[{"role": "system", "content": "Summarize the following text concisely."}, {"role": "user", "content": text}])
        return response['message']['content']
    except Exception as e:
        return f"Error: Unable to summarize text. {str(e)}"


# Call Ollama Chat Function
async def call_ollama(messages):
    """Handles interaction with Ollama API safely."""
    try:
        response = chat(model='hermes3:8b', messages=messages)
        return response['message']['content']
    except Exception as e:
        return f"Error: Unable to process request. {str(e)}"



@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user.name}')

@bot.command(name="hello")
async def hello(ctx):
        await ctx.send("Hello, I'm a bot!")

@commands.cooldown(1, 10, commands.BucketType.user)  # 1 request per 10 seconds per user
@bot.command(name="ask")
async def ask(ctx, *, message):
    await ctx.send("Processing your query...")
    
    user_id = ctx.author.id  # Unique identifier for each user

    # Retrieve conversation history or start a new one
    if user_id not in conversation_history:
        conversation_history[user_id] = [
            {
                'role': 'system',
                'content': 'You are a helpful assistant who strives to offer information and insights on whatever the user enquires. You can also be creative and thoughtful.',
            }
        ]

    # Append the new user message to history
    conversation_history[user_id].append({'role': 'user', 'content': message})

    # Keep only the last MAX_HISTORY messages
    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    # Call Ollama Bot
    bot_response = await call_ollama(conversation_history[user_id])

    # Append conversation History
    conversation_history[user_id].append({'role': 'assistant', 'content': bot_response})

    # Ensure the conversation history stays within the limit
    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    # Send response in chunks if necessary
    for chunk in [bot_response[i:i+2000] for i in range(0, len(bot_response), 2000)]:
        await ctx.send(chunk)

@ask.error
async def ask_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Please wait {error.retry_after:.2f} seconds before using this command again.")

@commands.cooldown(1, 20, commands.BucketType.user)  # 1 request per 20 seconds per user
@bot.command(name="askw")
async def askW(ctx, *, message):
    await ctx.send("Searching for additional information...")

    # Get web search results using Google PSE and fetch content
    search_results = await google_search(message)
    
    # Summarize search results
    summarized_results = await summarize_text(search_results)

    await ctx.send("Processing your query with summarized web data...")

    user_id = ctx.author.id

    # Retrieve or initialize conversation history
    if user_id not in conversation_history:
        conversation_history[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]

    conversation_history[user_id].append({"role": "user", "content": message})
    conversation_history[user_id].append({"role": "system", "content": f"Relevant summarized web search results:\n{summarized_results}"})

    # Keep only the last MAX_HISTORY messages
    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    bot_response = await call_ollama(conversation_history[user_id])

    conversation_history[user_id].append({"role": "assistant", "content": bot_response})
    conversation_history[user_id] = conversation_history[user_id][-10:]

    # Keep only the last MAX_HISTORY messages
    if len(conversation_history[user_id]) > MAX_HISTORY:
        conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY:]

    for chunk in [bot_response[i:i+2000] for i in range(0, len(bot_response), 2000)]:
        await ctx.send(chunk)

@askW.error
async def askW_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Please wait {error.retry_after:.2f} seconds before using this command again.")

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
