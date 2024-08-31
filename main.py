from nextcord.ext import commands, tasks
from nextcord import Interaction, SlashOption, ButtonStyle, ChannelType, SelectOption
from nextcord.errors import Forbidden
from nextcord.ui import Button, View, UserSelect, Select, TextInput, Modal
import nextcord
import requests
import base64
import os
import re
import json
from datetime import datetime
from io import BytesIO
import asyncio
import time
import aiohttp
import aiofiles

intents = nextcord.Intents.default()
intents.invites = True
intents.message_content = True
intents.members = True
intents.guilds = True
intents.bans = True
intents.moderation = True

client_discord = nextcord.Client(intents=intents)

try:
    with open('settings.json', 'r') as file:
        try:
            data = json.load(file)
            TOKEN = data["TOKEN"]
            whois_api_key = data["WHOIS"]
        except json.JSONDecodeError as e:
            print(f"Error while decoding: {e}")
except FileNotFoundError:
    with open('settings.json', 'w') as file:
        settings = {
            "TOKEN": "Enter your discord bot token",
            "WHOIS": "Enter you WHOIS api key"
        }
        json.dump(settings, file, indent=4)


async def save_icon(image_base64, filename):
    image_data = base64.b64decode(image_base64)
    file_path = os.path.join("images", filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(image_data)
    return file_path


async def save_favicon(favicon_data, filename):
    os.makedirs("icons", exist_ok=True)
    file_path = os.path.join("icons", f"{filename}.png")
    async with aiofiles.open(file_path, "wb") as file:
        await file.write(favicon_data.getvalue())
    return file_path


async def anticheat_read():
    file_path = os.path.join('Servers', 'Anticheats.json')

    if os.path.exists(file_path):
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                data = await file.read()
                return json.loads(data)
        except json.JSONDecodeError as e:
            print(f"Error reading JSON file: {e}")
            return None
    else:
        print(f"File not found: {file_path}")
        return None


async def location_emoji():
    file_path = os.path.join('Servers', 'Location.json')

    if os.path.exists(file_path):
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                data = await file.read()
                return json.loads(data)
        except json.JSONDecodeError as e:
            print(f'Error while reading JSON file: {e}')
            return None
    else:
        print(f'File not found {file_path}')
        return None


def cut_domain(server):
    server = re.sub(r'^https?://', '', server)
    server_parts = server.split('.')
    normalized_domain = '.'.join(server_parts[:-1])

    if len(server_parts) > 2:
        normalized_domain = server_parts[1]

    return normalized_domain


async def add_emoji(emoji_name, base64_image):
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://discord.com/api/v10/applications/{client_discord.application_id}/emojis",
                               headers=headers) as resp:
            emoji_list = await resp.json()
            emoji_list = emoji_list["items"]

        if emoji_list:
            is_exist = any(emoji["name"] == emoji_name for emoji in emoji_list)
            if is_exist:
                return "Emoji already exist", None
            else:
                data = {
                    "name": emoji_name.replace("-", "_"),
                    "image": f"data:image/png;base64,{base64_image}"
                }
                try:
                    async with session.post(
                            f"https://discord.com/api/v10/applications/{client_discord.application_id}/emojis",
                            headers=headers, json=data) as response:
                        response.raise_for_status()
                        emoji_id = (await response.json()).get('id')
                        return "Emoji added successfully", emoji_id
                except aiohttp.ClientError as e:
                    return f"Error adding emoji: {e}", None
        else:
            return "Unable to get emoji list", None


async def add_server(data, location, emoji_id):
    async with aiofiles.open("Servers/Anticheats.json", "r") as file:
        json_file = json.loads(await file.read())

    title = cut_domain(data["host"])
    if not any(json_file[key]["Title"] == title for key in json_file):
        new = {
            "Title": title,
            "Domain": data["host"],
            "Anticheat": "Not added (to file)",
            "Emoji": f"<:customemoji:{emoji_id}>",
            "Location": location["country"]
        }
        json_file[title] = new
        async with aiofiles.open('Servers/Anticheats.json', 'w') as file:
            await file.write(json.dumps(json_file, indent=4))


async def server_and_ip_info(domain):
    url = f'https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey={whois_api_key}&domainName={domain}&outputFormat=JSON'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as request:
            whois_data = await request.json()

    if 'WhoisRecord' in whois_data:
        return whois_data['WhoisRecord']
    else:
        return None


async def get_favicon(domain):
    favicon_url = f"https://{domain}/favicon.ico"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(favicon_url) as response:
                if response.status == 200:
                    favicon_base64 = base64.b64encode(await response.read()).decode('utf-8')
                    print('Favicon.ico found, sending')
                    return favicon_base64
                else:
                    print(f'Error while searching favicon.ico')
    except Exception as e:
        print(f'Error while getting favicon.ico: {e}')
        return None

    try:
        favicon_url = f"https://{domain}/favicon.png"
        async with aiohttp.ClientSession() as session:
            async with session.get(favicon_url) as response:
                if response.status == 200:
                    favicon_base64 = base64.b64encode(await response.read()).decode('utf-8')
                    print('Favicon.png found, sending')
                    return favicon_base64
                else:
                    print(f'Error while searching favicon.png')
    except Exception as e:
        print(f'Error while getting favicon.png: {e}')
        return None

    return None


@client_discord.event
async def on_ready():
    print(f'Logged as {client_discord.user}')


@client_discord.slash_command(name='minecraft-server-info', description='displays information about minecraft server')
async def serverinfo(interaction: Interaction,
                     server: str = SlashOption(name='ip',
                                               description='Please enter the full Minecraft server domain,'
                                                           ' e.g., play.server.com')):
    domain = cut_domain(server.lower())
    channel = interaction.channel
    channel_response = interaction.response
    anticheats = await anticheat_read()
    await channel_response.send_message('Wait for the bot to collect the information and send it to you', ephemeral=True)
    request = requests.get(f'https://api.mcstatus.io/v2/status/java/{server.lower()}')
    embed = nextcord.Embed(title=f'Information about {server}',
                           color=nextcord.Color.dark_grey())
    try:
        data = request.json()
        location = requests.get(f'http://ip-api.com/json/{data["ip_address"]}').json()
        print(location)
        print(data)

    except json.JSONDecodeError as e:
        embed.add_field(name="Error",
                        value=f"Something went wrong. Maybe you typed wrong ip or there is an error with the json file. {e}")
        await channel.send(embed=embed)
    if data["online"] is True and location["status"] == 'success':
        embed.add_field(name='Status: ', value='Active')
        embed.add_field(name='Domain: ', value=data["host"])
        embed.add_field(name='Ip address: ', value=f'{data["ip_address"]}\n({location["country"]},\n{location["city"]})')
        embed.add_field(name='Server version: ', value=data["version"]["name_clean"])
        embed.add_field(name='Online: ', value=f'{data["players"]["online"]}/{data["players"]["max"]}')
        if anticheats is None:
            embed.add_field(name='Anticheat: ', value='Unable to load anticheats data.')
        else:
            anticheat_info = anticheats.get(domain)
            if anticheat_info and anticheat_info.get("Anticheat") is not None:
                embed.add_field(name='Anticheat: ', value=anticheat_info["Anticheat"])
            else:
                embed.add_field(name='Anticheat: ', value='Information not found in database')
        if data["players"]["online"] >= 60:
            embed.add_field(name='Players list: ', value="Too much players sorry(")
        else:
            players_list = [member.get("name_clean", "Unknown") for member in data.get("players", {}).get("list", [])]
            if players_list:
                embed.add_field(name='Players list:', value="\n".join(players_list))
            else:
                embed.add_field(name='Players list:', value="No players found, or server hid the list")
        embed.add_field(name="Description: ", value=data["motd"]["clean"])
        if data["icon"]:
            print(data["icon"])
            image_base64 = data["icon"].split(",")[1]
            try:
                message, emoji_id = await add_emoji(cut_domain(data["host"]), image_base64)
                print(message)
                await add_server(data, location, emoji_id)
            except requests.exceptions.RequestException:
                print(f'Something went wrong while adding emoji with name: {cut_domain(data["host"])}')

            file_path = await save_icon(image_base64, f"{data['host']}.png")
            file = nextcord.File(file_path, filename=f"{data['host']}.png")
            embed.set_thumbnail(url=f"attachment://{data['host']}.png")
        embed.add_field(name='Requested: ', value=f'<t:{int(data["retrieved_at"] / 1000)}:R>')

        try:
            await channel.send(embed=embed, file=file)
        except nextcord.errors.NotFound:
            await channel.send(f'Something went wrong, try again please')
        except UnboundLocalError:
            await channel.send(embed=embed)
    elif location["status"] == 'success':
        print(location)
        print(data)
        embed.add_field(name="Status: ", value=f"Currently server offline\n"
                                               f'Ip: {data["ip_address"]}\n({location["country"]},\n{location["city"]})\n')
        try:
            await channel.send(embed=embed)
        except nextcord.errors.NotFound:
            await channel.send(f'Something went wrong, try again please')
    else:
        embed.add_field(name="Status: ", value="invalid domain wrote")
        try:
            await channel.send(embed=embed)
        except nextcord.errors.NotFound:
            await channel.send(f'Something went wrong, try again please')


@client_discord.slash_command(name='server-info', description='Displays information about server or IP')
async def serverinfo(interaction: Interaction,
                     server: str = SlashOption(name='ip',
                                               description='Please enter the full server domain or IP,'
                                                           ' e.g., server.com, 1.1.1.1')):
    channel = interaction.channel
    channel_response = interaction.response
    await channel_response.send_message(f'Wait for the bot to collect the information and send it to you', ephemeral=True)
    data = await server_and_ip_info(server)

    embed = nextcord.Embed(title=f'Information about {server}',
                           color=nextcord.Color.dark_grey())
    embed.set_footer(text=f'Requested by: {interaction.user.name}', icon_url=interaction.user.avatar.url)

    favicon_base64 = await get_favicon(server.lower())
    if favicon_base64:
        try:
            favicon_data = BytesIO(base64.b64decode(favicon_base64))
            file_path = await save_favicon(favicon_data, server)
            if os.path.exists(file_path):
                file = nextcord.File(file_path, filename="favicon.png")
                embed.set_thumbnail(url="attachment://favicon.png")
            else:
                print(f"Favicon file not found at path: {file_path}")
                file = None
        except Exception as e:
            print(f"Failed to decode base64 or create file: {e}")
            file = None
    else:
        file = None

    embed.add_field(name='Domain: ', value=data.get("domainName", 'Domain not found'))
    embed.add_field(name='Registered service: ', value=data.get("registrarName", 'Registrar not found'))
    embed.add_field(name='IP addresses: ',
                    value=', '.join(
                        data.get("registryData", {}).get("nameServers", {}).get("ips", [])) or 'No IP addresses found')
    embed.add_field(name='Status: ', value=data.get("registryData", {}).get("status", 'Status not found'))

    registrant = data.get("registryData", {}).get("registrant", {})
    embed.add_field(name='Registered by (name): ', value=registrant.get("name", 'Registrant name not found'))
    embed.add_field(name='Registered by (email): ', value=registrant.get("email", 'Registrant email not found'))

    created_date = data.get("registryData", {}).get("createdDate", "")
    expires_date = data.get("registryData", {}).get("expiresDate", "")

    embed.add_field(name='Registered at: ',
                    value=(f'<t:{int(datetime.fromisoformat(created_date.replace("Z", "+00:00")).timestamp())}:F>'
                           if created_date else 'Registration date not found'))
    embed.add_field(name='Expires at: ',
                    value=(f'<t:{int(datetime.fromisoformat(expires_date.replace("Z", "+00:00")).timestamp())}:F>'
                           if expires_date else 'Expiration date not found'))

    try:
        if file:
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)
    except nextcord.errors.NotFound:
        await channel_response.send_message('Something went wrong, try again please', ephemeral=True)


@client_discord.slash_command(name='minecraft-servers', description='Displays list of servers and their anticheats')
async def serverinfo_list(interaction: Interaction):
    channel = interaction.channel
    user = interaction.user
    data = await anticheat_read()
    print("-" * 1000)
    print(f'Requested by {user.name}')
    if data is None:
        return
    await interaction.response.send_message('Wait for the bot to collect the information and send it to you', ephemeral=True)
    await client_discord.change_presence(status=nextcord.Status.do_not_disturb)
    servers = list(data.keys())
    chunk_size = 25
    chunks = [servers[i:i + chunk_size] for i in range(0, len(servers), chunk_size)]
    response_time = time.monotonic()
    async with aiohttp.ClientSession() as session:
        for chunk in chunks:
            embed = nextcord.Embed(title='Servers list', color=nextcord.Color.dark_grey())
            embed.set_footer(text=f"Requested by: {user.name}\n", icon_url=user.avatar.url)
            for server_name in chunk:
                server = data[server_name]

                try:
                    start_time = time.monotonic()
                    async with session.get(f'https://api.mcstatus.io/v2/status/java/{server["Domain"].lower()}') as request:
                        data_server = await request.json()
                    async with session.get(f'http://ip-api.com/json/{data_server["ip_address"]}') as request:
                        location = await request.json()
                    end_time = time.monotonic()
                    print(f'Response: is server active: {data_server["online"]} ({data_server["host"]}), location: {location["status"]}, Ip: {data_server["ip_address"]}, Elapsed: {end_time-start_time:.2f}s')
                except Exception as e:
                    print(f'Error: {e}')
                    continue
                await asyncio.sleep(0.5)
                country = location["country"]
                try:
                    country_emoji = await location_emoji()
                except json.JSONDecodeError:
                    country = "Other"
                if 'players' in data_server and location["status"] == 'success':
                    server_info = (
                        f'Anticheat: {server["Anticheat"]}\n'
                        f'Location: {location["country"]},\n{location["city"]}\n'
                        f'Ip address: {data_server["ip_address"]}\n'
                        f'Online: {data_server["players"].get("online", "Server offline")}/{data_server["players"].get("max", "Server offline")}'
                    )
                elif location["status"] == 'success':
                    server_info = (
                        f'Anticheat: {server["Anticheat"]}\n'
                        f'Location: {location["country"]},\n{location["city"]}\n'
                        f'Ip address: {data_server["ip_address"]}\n'
                        f'Online: Server currently offline'
                    )
                else:
                    server_info = (
                        f'Anticheat: {server["Anticheat"]}\n'
                        f'Location: Server currently offline\n'
                        f'Ip address: {data_server["ip_address"]}\n'
                        f'Online: Server currently offline'
                    )

                embed.add_field(name=f'{server["Emoji"]} {server["Title"]} {country_emoji[country]["Emoji"]}\n ({server["Domain"]})', value=server_info, inline=True)

            await channel.send(embed=embed)
            await asyncio.sleep(1)
        send_time = time.monotonic()
        print(f'Takes: {send_time-response_time:.2f}s')
        await client_discord.change_presence(status=nextcord.Status.online)

try:
    client_discord.run(TOKEN)
except NameError:
    print(f'Please open "settings.json" and enter TOKEN AND WHOIS parameters')
