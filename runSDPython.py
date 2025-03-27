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

load_dotenv()

# discord intents
intents =  discord.Intents.default()
intents.message_content = True
bot =  commands.Bot(command_prefix="/", intents=intents)

server_address = "host.docker.internal:8188"
#server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())



@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user.name}')
    channel = bot.get_channel(1353257157734305852)
    if channel:
        await channel.send("✅ Bot is now **ONLINE**!")

@bot.command(name="img")
async def ask(ctx, *, message):
    await ctx.send("Received request, processing...")
    images1 = await main_trigger(message)  # Call the function and get images
    images2 = await main_trigger(message)  # Call the function and get images
    if images1:
        for node_id in images1:
            for image_data in images1[node_id]:
                image = Image.open(io.BytesIO(image_data))  # Open image from bytes
                
                # Save the image to a BytesIO buffer
                img_buffer = io.BytesIO()
                image.save(img_buffer, format="PNG")  # Save image in PNG format
                img_buffer.seek(0)  # Move pointer to the beginning
                
                # Send the image as a Discord file
                file = discord.File(img_buffer, filename="image.png")
                await ctx.send("Here is your image1:", file=file)
    else:
        await ctx.send("Failed to generate an image.")

    if images2:
        for node_id in images2:
            for image_data in images2[node_id]:
                image = Image.open(io.BytesIO(image_data))  # Open image from bytes
                
                # Save the image to a BytesIO buffer
                img_buffer = io.BytesIO()
                image.save(img_buffer, format="PNG")  # Save image in PNG format
                img_buffer.seek(0)  # Move pointer to the beginning
                
                # Send the image as a Discord file
                file = discord.File(img_buffer, filename="image.png")
                await ctx.send("Here is your image2:", file=file)
    else:
        await ctx.send("Failed to generate an image.")

    url = "http://host.docker.internal:8188/free"
    data = {"unload_models": True, "free_memory": False}

    response = requests.post(url, json=data)
    print("Response:", response.status_code, response.text)


  




def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        print("Error Code:", e.code)
        print("Error Message:", e.read().decode())  # Print server response
        raise

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            # If you want to be able to decode the binary stream for latent previews, here is how you can do it:
            # bytesIO = BytesIO(out[8:])
            # preview_image = Image.open(bytesIO) # This is your preview in PIL image format, store it in a global
            continue #previews are binary data

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


async def main_trigger(messages):  
    prompt_text = """
    {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 3.0,
                "denoise": 1,
                "latent_image": [
                    "5",
                    0
                ],
                "model": [
                    "4",
                    0
                ],
                "negative": [
                    "7",
                    0
                ],
                "positive": [
                    "6",
                    0
                ],
                "sampler_name": "dpmpp_sde",
                "scheduler": "sgm_uniform",
                "seed": 444,
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "PONY\\\\duchaitenPonyReal_v20.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": 768,
                "width": 1344
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "10",
                    0
                ],
                "text": "masterpiece best quality girl"
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "10",
                    0
                ],
                "text": "score_5, score_4, low quality, worst quality, blur, blurry, text, signature, watermark, extra limbs, deformed hands, bad anatomy, bad fingers"
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [
                    "3",
                    0
                ],
                "vae": [
                    "4",
                    2
                ]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": [
                    "8",
                    0
                ]
            }
        },
        "10": {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -2,
                "clip": [
                    "4",
                    1
                ]
            }
        }
    }
    """

    prompt = json.loads(prompt_text)
    #set the text prompt for our positive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = messages

    #set the seed for our KSampler node
    prompt["3"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)  # Generates a random 32-bit integer
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))

    images = get_images(ws, prompt)
    ws.close() # for in case this example is used in an environment where it will be repeatedly called, like in a Gradio app. otherwise, you'll randomly receive connection timeouts
    #Commented out code to display the output images:

    return images

bot.run(os.getenv('DISCORD_BOT_TOKEN'))
