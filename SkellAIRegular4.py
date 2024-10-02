import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import OpenAI
import pathlib
import random
import asyncio
import datetime
import re
import aiohttp
from bs4 import BeautifulSoup
import requests

# Load environment variables
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
DISCORD_EXPORTS_PATH = os.getenv('DISCORD_LOGS_PATH')  # Path to the folder containing JSON exports
CHANNEL_REMEMBERANCE = int(os.getenv('CHANNEL_REMEMBERANCE'))
LLM_MODEL = os.getenv('LLM_MODEL')


VISION_MODEL = os.getenv('VISION_MODEL')

from SYSTEMMESSAGES import *
from skellymessages1 import *
from system_prompt import SYSTEM_PROMPT

# Initialize OpenAI client with OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Initialize the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

conversation_dir = "conversations"
pathlib.Path(conversation_dir).mkdir(parents=True, exist_ok=True)

def get_conversation_file_path(username):
    sanitized_username = "".join(c for c in username if c.isalnum() or c in (' ','.','_')).rstrip()
    return os.path.join(conversation_dir, f"{sanitized_username}.txt")

def read_conversation(username):
    file_path = get_conversation_file_path(username)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.readlines()
    return []

def write_conversation(username, conversation_lines):
    file_path = get_conversation_file_path(username)
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(str(conversation_lines))

if False:
    def load_skelly_messages(max_messages=10000):
        skelly_messages = []
        file_count = 0
        skelly_message_count = 0
        one_year_ago = datetime.now(tzutc()) - timedelta(days=365)

        for filename in os.listdir(DISCORD_EXPORTS_PATH):
            if filename.endswith('.json'):
                file_count += 1
                print(f"Processing file {file_count}: {filename}")
                try:
                    with open(os.path.join(DISCORD_EXPORTS_PATH, filename), 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        if 'messages' not in data:
                            print(f"  File {filename} does not contain a 'messages' key. Structure: {list(data.keys())}")
                            continue
                        for message in data['messages']:
                            if 'author' not in message or 'name' not in message['author'] or 'timestamp' not in message:
                                continue
                            
                            try:
                                message_time = parse(message['timestamp'])
                            except ValueError:
                                print(f"  Invalid timestamp format in {filename}: {message['timestamp']}. Skipping message.")
                                continue

                            if message_time < one_year_ago:
                                continue

                            if message['author']['name'] == 'skellia':
                                skelly_message_count += 1
                                content = message.get('content', '').strip()
                                if content:
                                    skelly_messages.append(content)
                                    print(f"  Found Skelly message {skelly_message_count}: {content[:50]}...")
                                    if len(skelly_messages) >= max_messages:
                                        print(f"Reached max messages ({max_messages}). Stopping.")
                                        print(f"Processed {file_count} files.")
                                        return skelly_messages
                except Exception as e:
                    print(f"Error processing file {filename}: {str(e)}. Skipping.")
        
        print(f"Processed {file_count} files.")
        print(f"Found {skelly_message_count} Skelly messages total.")
        print(f"Loaded {len(skelly_messages)} unique Skelly messages.")
        print("First few messages:", skelly_messages[:5])
        return skelly_messages

# Load Skelly messages when the bot starts
import ast

def load_messages_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            skelly_messages = content
        return skelly_messages
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except SyntaxError:
        print(f"Error: Invalid syntax in the file {file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

file_path = 'C:/Misc/SCORP3/systemmessages.txt'  # Replace with the actual path to your file
#skelly_messages = load_messages_from_file(file_path)

#if skelly_messages:
    #print(f"Loaded {len(skelly_messages)} messages.")
    #print("First few messages:")
    #for messages in skelly_messages[:5]:
     #   print(messages)
        
skelly_messages = SYSTEMMESSAGES
skelly_zone_messages = SKELLYZONEMESSAGES
#print(skelly_zone_messages)

#load_skelly_messages(10000)
#print(load_skelly_messages(10000))

# Dictionary to store cooldown times for each channel
channel_cooldowns = {}

async def get_channel_history(channel, hours=6):
    six_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    messages = []
    async for message in channel.history(limit=None, after=six_hours_ago):
        messages.append(f"{message.author.name}: {message.content}")
    return messages

import logging

# Set up logging
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def analyze_image(image_url):
    try:
        image_analysis = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this image briefly."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ],
            max_tokens=100,
            stream=False
        )
        return image_analysis.choices[0].message.content
    except Exception as e:
        logging.error(f"Error analyzing image: {str(e)}")
        return "I couldn't analyze the image properly."

def extract_emojis(text):
    emoji_pattern = r'£(.*?)£'
    return re.findall(emoji_pattern, text)

def rewriter(line, random_skelly_messages):
    new_message = [
        {"role": "system", "content": f"Only reply with the final rewritten content, nothing else. You must rewrite messages in the speaking style of Skelly. Here are some example messages from Skelly to help you understand and emulate their speaking style: <skelly_messages>\n{random_skelly_messages}\n</skelly_messages>"},
        {"role": "Message to Rewrite", "content": f"Rewrite these messages in Skelly's speaking style whilst keeping the formatting the same: {line}"}
    ]

    completion = client.chat.completions.create(
        model=LLM_MODEL,
        messages=new_message,
        max_tokens=250,
        temperature=0.5,
        stream=False
    )
    if completion.choices[0].message.content == None:
        return line
    else:
        ai_response = completion.choices[0].message.content
        print("Rewriter: ", ai_response)
        return ai_response

    return line



# Regular expression to detect URLs in the message
URL_REGEX = r'(https?://\S+)'

async def fetch_url_info(url):
    """Fetch content from the given URL."""
    if 'twitter.com' in url:
        url = url.replace('fxtwitter', 'x')
        url = url.replace('vxtwitter', 'x')
        return await scrape_twitter_tweet(url)
    if 'x.com' in url:
        return await scrape_twitter_tweet(url)
    else:
        return await scrape_webpage(url)

def extract_tweet_id(url):
    """Extract the tweet ID from a Twitter (or FX Twitter) URL."""
    # Regular expression to match the tweet ID
    match = re.search(r'/status/(\d+)', url)
    if match:
        return match.group(1)  # Return the captured group (the tweet ID)
    else:
        return None  # Return None if no match is found

async def scrape_twitter_tweet(url):
    """Scrape specific tweet information from the Twitter URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                id = extract_tweet_id(url)
                api_url = f"https://cdn.syndication.twimg.com/tweet-result?id={id}&token=a"

                async with session.get(api_url) as api_response:
                    if api_response.status == 200:
                        data = await api_response.json()

                        # Extract tweet text and user handle
                        tweet_text = data["text"]
                        user_handle = data["user"]["screen_name"]  # Updated key access
                        media = data["mediaDetails"]

                        # Extract image links
                        image_links = [media_item["media_url_https"] for media_item in media]

                        # Analyze images and get descriptions
                        image_descriptions = []
                        for image_link in image_links:
                            description = await analyze_image(image_link)  # Assuming analyze_image returns a description
                            image_descriptions.append(description)

                        return (f"User: {user_handle}\nTweet: {tweet_text}\n"
                                f"Image Descriptions: {' | '.join(image_descriptions) if image_descriptions else 'No images found'}")
                    else:
                        return f"Failed to retrieve tweet data from API, status code: {api_response.status}"
            else:
                return f"Failed to retrieve tweet from {url}, status code: {response.status}"


async def scrape_webpage(url):
    """General method to scrape webpage content such as title, description, author, h1 headers, and full text."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract the page title
                title = soup.title.string if soup.title else 'No title found'

                # Extract meta description, fallback to Open Graph description if available
                meta_description = soup.find('meta', attrs={'name': 'description'})
                og_description = soup.find('meta', property='og:description')
                description = (meta_description['content'] if meta_description else
                               og_description['content'] if og_description else
                               'No description found')

                # Extract author information
                meta_author = soup.find('meta', attrs={'name': 'author'})
                og_author = soup.find('meta', property='article:author')
                author_tag = soup.find(attrs={"class": "author-name"})
                author = (meta_author['content'] if meta_author else
                          og_author['content'] if og_author else
                          author_tag.get_text(strip=True) if author_tag else 'No author found')

                # Extract H1 headers
                h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
                h1_content = ' | '.join(h1_tags) if h1_tags else 'No H1 headers found'

                # Extract full text content from paragraphs
                paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
                full_text = '\n'.join(paragraphs) if paragraphs else 'No text content found'

                return (f"Title: {title}\nDescription: {description}\nAuthor: {author}\n"
                        f"H1: {h1_content}\nFull Text: {full_text[:500]}...")  # Limiting text to 500 chars
            else:
                return f"Failed to retrieve content from {url}, status code: {response.status}"

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message) or (random.random() < 0.1):
        user = ""
        if message.author != None:
            user = message.author

        username = ""
        if user.name != None:
            username = user.name
        
        nickname = ""
        if user.nick != None:
            nickname = user.nick

        userid = ""
        if user.id != None:
            userid = user.id  
        
        random_skelly_messages = random.sample(skelly_messages, min(400, len(skelly_messages))) + random.sample(skelly_zone_messages, min(400, len(skelly_zone_messages)))

        channel_history = await get_channel_history(message.channel)
        context = "\n".join(channel_history[-CHANNEL_REMEMBERANCE:])

        query_text = f"{username}'s Nickname on this Server: {nickname}\n\n{username}'s user_id: {userid}\n\n{username}'s message: {message.content}"
        context = f"Context of recent messages in the #{message.channel} channel:\n{context}\n\n"

        print("\n\n\n")
        print(context)

        print("\n\n\n")
        print(query_text)
        
        # Detect URLs in the message
        urls = re.findall(URL_REGEX, message.content)
        url_info = []

        # Fetch information from each URL
        for url in urls:
            url_content = await fetch_url_info(url)
            url_info.append(f"Info from {url}: {url_content[:200]}")  # limiting the amount of content shown
            print(url_info)

        if url_info:
            query_text += f"\n\nExtracted information from URLs: {' '.join(url_info)}"

        image_descriptions = []
        for attachment in message.attachments:
            if attachment.content_type.startswith('image'):
                image_description = await analyze_image(attachment.url)
                image_descriptions.append(image_description)
        
        if image_descriptions:
            query_text += f"\n\nImage descriptions: {' '.join(image_descriptions)}"


        image_descriptions = []
        for attachment in message.attachments:
            if attachment.content_type.startswith('image'):
                image_description = await analyze_image(attachment.url)
                image_descriptions.append(image_description)
        
        if image_descriptions:
            query_text += f"\n\nImage descriptions: {' '.join(image_descriptions)}"


        try:
            conversation_lines = read_conversation(username)
            parsed_conversation = []

            for i, line in enumerate(conversation_lines):
                role = "Other Person" if i % 2 == 0 else "You"
                parsed_conversation.append({"role": role, "content": line})

            #parsed_conversation.append({"role": "system", "content": "Emulate and copy Skelly's writing style. Be a bit cute. Copy Skelly's writing style and use the same grammar as Skelly. Don't act like an AI assistant. Don't repeat yourself or copy the style of your previous messages."})
            parsed_conversation.append({"role": "Recent Discord Channel History", "content": context})
            parsed_conversation.append({"role": f"{username}|{nickname}|{userid}", "content": query_text})

            system_message = SYSTEM_PROMPT.format(random_skelly_messages="\n".join(random_skelly_messages))

            messages = [
                {"role": "system", "content": system_message},
                *parsed_conversation
            ]

            completion = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                max_tokens=250,
                temperature=0.,
                stream=False
            )


            if completion.choices[0].message.content is None:
                await message.channel.send("‎ ", reference=message, mention_author=False)
                return

            ai_response = completion.choices[0].message.content+"‎"
            print("\n\n\n\n\n\n")
            print(f"Generated response: {ai_response}")

            #new_message = [
            #    {"role": "system", "content": f"Only reply with the final rewritten message, nothing else. You must rewrite messages in the speaking style of Skelly. Here are some example messages from Skelly to help you understand and copy their speaking style: <skelly_messages>\n{random_skelly_messages}\n</skelly_messages>. Be a bit cute. Copy Skelly's writing style and use the same grammar as Skelly.."},
            #    {"role": "Message to Rewrite", "content": f"Rewrite this message in Skelly's speaking style: {ai_response}"}
            #]

            #completion = client.chat.completions.create(
            #    model=LLM_MODEL,
            #    messages=new_message,
            #    max_tokens=250,
            #    temperature=0.5,
            #    stream=False
            #)

            if len(completion.choices[0].message.content) < 1:
                ai_response = "."
            else:
                ai_response = completion.choices[0].message.content+"‎"

            should_react_star = "st4r" in ai_response.lower()
            ai_response = re.sub(r'st4r', '\-# *starred*\n', ai_response, flags=re.IGNORECASE)

            emojis_to_react = extract_emojis(ai_response)
            ai_response = re.sub(r'£.*?£', '\n-# *reacted*\n', ai_response)

            sent_message = await message.channel.send(ai_response, reference=message, mention_author=False)

            if should_react_star:
                await message.add_reaction("⭐")

            for emoji in emojis_to_react:
                try:
                    await message.add_reaction(emoji.strip())
                except discord.errors.HTTPException:
                    logging.warning(f"Failed to add reaction: {emoji}")

            new_message_content = query_text.replace('\n', '  ').replace('\r', '  ')
            new_ai_response = ai_response.replace('\n', '  ').replace('\r', '  ')
            write_conversation(username, f'{username}|{nickname}|{userid}: {new_message_content}\n')
            write_conversation(username, f'{new_ai_response}\n')

            if "REALRESET" in message.content:
                await message.channel.send("RESET")
                file_path = get_conversation_file_path(username)
                if os.path.exists(file_path):
                    os.remove(file_path)

        except Exception as e:
            logging.error(f"Error in on_message: {str(e)}", exc_info=True)
            print(f"An error occurred: {str(e)}")

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


bot.run(DISCORD_BOT_TOKEN)
