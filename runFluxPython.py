import websocket
import uuid
import json
import urllib.request
import urllib.parse
import time
from PIL import Image
import io
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import random
import asyncio

load_dotenv()

# discord intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

#server_address = "host.docker.internal:8188"
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user.name}')
    channel = bot.get_channel(1353257157734305852)
    if channel:
        await channel.send("✅ Bot is now **ONLINE**!")

@commands.cooldown(1, 10, commands.BucketType.user)  # 1 request per 10 seconds per user
@bot.command(name="img")
async def ask(ctx, *, message):
    await ctx.send("Received request, processing...")
    try:
        images1 = await main_trigger(message, ctx)
        images2 = await main_trigger(message, ctx)

        await send_images(ctx, images1, "image1")
        await send_images(ctx, images2, "image2")

        url = f"http://{server_address}/free"
        data = {"unload_models": True, "free_memory": False}
        response = requests.post(url, json=data)
        print("Response:", response.status_code, response.text)

    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

async def send_progress(ctx, progress_event):
    start_time = time.time()  # Store the start time
    message = await ctx.send(f"⏳ Generating image...")
    while not progress_event.is_set():
        await asyncio.sleep(10)
        elapsed_time = int(time.time() - start_time)  # Calculate elapsed time
        await message.edit(content=f"⏳ Still generating... Please wait!(Elapsed time: {elapsed_time}s)")

async def async_get_images(prompt, ctx):
    loop = asyncio.get_event_loop()
    progress_event = asyncio.Event()

    # Start progress updates
    progress_task = asyncio.create_task(send_progress(ctx, progress_event))

    images = await loop.run_in_executor(None, sync_get_images, prompt, ctx, progress_event)

    # Ensure the progress task stops
    await progress_event.wait()  # Wait for signal
    progress_task.cancel()
    try:
        await progress_task  # Ensure it cancels cleanly
    except asyncio.CancelledError:
        pass

    return images

def sync_get_images(prompt, ctx, progress_event):
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
    images = asyncio.run(get_images(ws, prompt,ctx, progress_event))
    ws.close()
    return images


async def send_images(ctx, images, message_prefix):
    if images:
        for node_id in images:
            for image_data in images[node_id]:
                image = Image.open(io.BytesIO(image_data))
                img_buffer = io.BytesIO()
                image.save(img_buffer, format="PNG")
                img_buffer.seek(0)
                file = discord.File(img_buffer, filename="image.png")
                await ctx.send(f"Here is your {message_prefix}:", file=file)
    else:
        await ctx.send("Failed to generate an image.")

def queue_prompt(prompt):
    print(f'Bot is in queue_prompt')
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print("Error Code:", e.code)
        print("Error Message:", e.read().decode())
        raise

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

async def get_images(ws, prompt, ctx, progress_event):
    print(f'Bot is in get_images')
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
        else:
            continue  # Previews are binary data

    # Signal that processing is done
    progress_event.set()

    print(f'Bot is getting history picture')
    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images

async def main_trigger(messages, ctx):
    prompt_text = """
    {
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "flux1-dev-Q4_K_S.gguf"
            }
        },
        "2": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                "type": "flux"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors"
            }
        },
        "4": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {
                "width": "896",
                "height": "1152",
                "batch_size": "1"
            }
        },
        "5": {
            "class_type": "ModelSamplingFlux",
            "inputs": {
                "model": ["1",0],
                "width": "896",
                "height": "1152",
                "max_shift": "1.0",
                "base_shift": "0.5"
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "2",
                    0
                ],
                "text": "masterpiece best quality girl"
            }
        },
        "7": {
            "class_type": "FluxGuidance",
            "inputs": {
                "conditioning": [
                    "6",
                    0
                ],
                "guidance": "3.0"
            }
        },
        "8": {
            "class_type": "FluxSampler",
            "inputs": {
                "denoise": 1,
                "latent_image": [
                    "4",
                    0
                ],
                "model": [
                    "5",
                    0
                ],
                "conditioning": [
                    "7",
                    0
                ],
                "sampler_name": "dpmpp_2m",
                "scheduler": "sgm_uniform",
                "noise_seed": 444,
                "steps": 20
            }
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [
                    "8",
                    0
                ],
                "vae": [
                    "3",
                    0
                ]
            }
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": [
                    "9",
                    0
                ]
            }
        }
    }
    """

    prompt = json.loads(prompt_text)
    # set the text prompt for our positive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = messages

    # set the seed for our KSampler node
    prompt["8"]["inputs"]["noise_seed"] = random.randint(0, 2**32 - 1)  # Generates a random 32-bit integer

    images = await async_get_images(prompt, ctx)
    return images

bot.run(os.getenv('DISCORD_BOT_TOKEN'))
