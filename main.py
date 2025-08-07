import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import os
import random
import json
import feedparser
import math
import aiohttp
from discord.ui import View, Select
from collections import defaultdict

# --- Mantener vivo el bot en Render/Replit ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Cliente principal con commands.Bot ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# --- Canales y datos ---
CANAL_SUGERENCIAS = 1108242948879028334
CANAL_NIVELES = 1400694590327095378
CANAL_YOUTUBE = 1100279149236600882  # Canal para notificaciones de YouTube

# --- API OpenWeather ---
OPENWEATHER_API_KEY = "6b5eabc5ef33b403c00a216e21366bc1"

# --- Sistema de niveles ---
DATA_FILE = "niveles.json"

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        niveles = json.load(f)
else:
    niveles = {}

def guardar_datos():
    with open(DATA_FILE, "w") as f:
        json.dump(niveles, f, indent=4)

# --- Sistema YouTube ---
YOUTUBE_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UC2OiC1E-tHN-IAO7RQINk_g"
ultimo_video_id = None


# ------------------------------
# EVENTOS
# ------------------------------

@bot.event
async def on_ready():
    await bot.tree.sync() 
    revisar_youtube.start()
    print(f"✅ Bot conectado como {bot.user}")



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)

    if user_id not in niveles:
        niveles[user_id] = {"xp": 0, "nivel": 1}

    xp_ganado = random.randint(5, 15)
    niveles[user_id]["xp"] += xp_ganado

    xp_necesario = niveles[user_id]["nivel"] * 100

    if niveles[user_id]["xp"] >= xp_necesario:
        niveles[user_id]["nivel"] += 1
        niveles[user_id]["xp"] -= xp_necesario

        canal = bot.get_channel(CANAL_NIVELES)
        if canal:
            await canal.send(
                f"🎉 {message.author.mention} ha subido al **nivel {niveles[user_id]['nivel']}**!"
            )

    guardar_datos()

    await bot.process_commands(message)


# ------------------------------
# TAREA PARA REVISAR YOUTUBE
# ------------------------------

@tasks.loop(minutes=5)
async def revisar_youtube():
    global ultimo_video_id
    feed = feedparser.parse(YOUTUBE_FEED)

    if feed.entries:
        nuevo_video = feed.entries[0]  # El más reciente
        video_id = nuevo_video.yt_videoid

        if ultimo_video_id != video_id:
            ultimo_video_id = video_id

            canal = bot.get_channel(CANAL_YOUTUBE)
            if canal:
                titulo = nuevo_video.title
                url = nuevo_video.link
                descripcion = getattr(nuevo_video, "media_description", "¡Nuevo video disponible!")

                embed = discord.Embed(
                    title=titulo,
                    url=url,
                    description=descripcion,
                    color=discord.Color.red()
                )
                embed.set_author(name="🎥 ¡Nuevo video en el canal!")
                if hasattr(nuevo_video, "media_thumbnail"):
                    embed.set_thumbnail(url=nuevo_video.media_thumbnail[0]['url'])

                await canal.send(embed=embed)


# ------------------------------
# COMANDOS
# ------------------------------

# /sugerencia
@bot.tree.command(name="sugerencia", description="Envía una sugerencia al servidor", extras={"categoria": "Utilidad"})
async def sugerencia(interaction: discord.Interaction, texto: str):
    if interaction.channel.id != CANAL_SUGERENCIAS:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en el canal de sugerencias.",
            ephemeral=True
        )
        return

    sugerencia_id = "".join([str(random.randint(0, 9)) for _ in range(8)])

    embed = discord.Embed(
        description=f"*Servidor: ChoreIsland*\n*Usuario: {interaction.user.display_name}*",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Sugerencia:", value=texto, inline=False)
    embed.set_footer(text=f"ID de sugerencia: {sugerencia_id}")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    await message.add_reaction("✅")
    await message.add_reaction("❌")


# /ping
@bot.tree.command(name="ping", description="Responde con Pong y el ping del bot", extras={"categoria": "Información"})
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latencia: {latency}ms")


# /clear
@bot.tree.command(name="clear", description="Borra mensajes recientes (solo admins)", extras={"categoria": "Moderación"})
@app_commands.describe(cantidad="Cantidad de mensajes a borrar (máximo 100)")
async def clear(interaction: discord.Interaction, cantidad: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return
    if cantidad < 1 or cantidad > 100:
        await interaction.response.send_message("❌ Debes borrar entre 1 y 100 mensajes.", ephemeral=True)
        return
    await interaction.response.defer()
    deleted = await interaction.channel.purge(limit=cantidad)
    await interaction.followup.send(f"🧹 He borrado {len(deleted)} mensajes.", ephemeral=True)


# /serverinfo
@bot.tree.command(name="serverinfo", description="Muestra información del servidor", extras={"categoria": "Información"})
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Información de {guild.name}", color=discord.Color.gold())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="ID", value=guild.id, inline=True)
    embed.add_field(name="Dueño", value=str(guild.owner), inline=True)
    embed.add_field(name="Miembros", value=guild.member_count, inline=True)
    embed.add_field(name="Canales", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Creado el", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    await interaction.response.send_message(embed=embed)


# /ban
@bot.tree.command(name="ban", description="Banea a un usuario (solo admins)", extras={"categoria": "Moderación"})
@app_commands.describe(usuario="Usuario a banear", razon="Razón del baneo")
async def ban(interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return
    try:
        await usuario.ban(reason=razon)
        await interaction.response.send_message(f"✅ {usuario.display_name} ha sido baneado.\nRazón: {razon}")
    except Exception as e:
        await interaction.response.send_message(f"❌ No pude banear a {usuario.display_name}.\nError: {e}", ephemeral=True)


# /kick
@bot.tree.command(name="kick", description="Expulsa a un usuario (solo admins)", extras={"categoria": "Moderación"})
@app_commands.describe(usuario="Usuario a expulsar", razon="Razón de la expulsión")
async def kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "No especificada"):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return
    try:
        await usuario.kick(reason=razon)
        await interaction.response.send_message(f"✅ {usuario.display_name} ha sido expulsado.\nRazón: {razon}")
    except Exception as e:
        await interaction.response.send_message(f"❌ No pude expulsar a {usuario.display_name}.\nError: {e}", ephemeral=True)


# /nivel
@bot.tree.command(name="nivel", description="Muestra tu nivel y XP", extras={"categoria": "Utilidad"})
async def nivel(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    user_id = str(usuario.id)

    if user_id not in niveles:
        await interaction.response.send_message(f"❌ {usuario.display_name} aún no tiene XP.", ephemeral=True)
        return

    xp = niveles[user_id]["xp"]
    nivel_actual = niveles[user_id]["nivel"]
    xp_necesario = nivel_actual * 100

    embed = discord.Embed(
        title=f"📊 Nivel de {usuario.display_name}",
        description=f"**Nivel:** {nivel_actual}\n**XP:** {xp}/{xp_necesario}",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


# /toplevels
@bot.tree.command(name="toplevels", description="Muestra el top de jugadores con más nivel", extras={"categoria": "Utilidad"})
async def toplevels(interaction: discord.Interaction):
    if not niveles:
        await interaction.response.send_message("❌ Aún no hay datos de XP.", ephemeral=True)
        return

    # Ordenar por nivel y XP
    top = sorted(niveles.items(), key=lambda x: (x[1]["nivel"], x[1]["xp"]), reverse=True)[:10]

    descripcion = ""
    for i, (user_id, datos) in enumerate(top, start=1):
        usuario = await bot.fetch_user(int(user_id))
        descripcion += f"**#{i}** {usuario.display_name} → Nivel {datos['nivel']} ({datos['xp']} XP)\n"

    embed = discord.Embed(
        title="🏆 Top Jugadores",
        description=descripcion,
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)


# /help
@bot.tree.command(name="help", description="Muestra la lista de comandos por categoría", extras={"categoria": "Utilidad"})
async def help_command(interaction: discord.Interaction):
    categorias = defaultdict(list)

    for command in tree.get_commands():
        categoria = command.extras.get("categoria", "Otros")
        categorias[categoria].append(command)

    categorias_visibles = {}
    for cat, comandos in categorias.items():
        if cat == "Moderación" and not interaction.user.guild_permissions.administrator:
            continue
        categorias_visibles[cat] = comandos

    select = Select(
        placeholder="Selecciona una categoría",
        options=[discord.SelectOption(label=cat) for cat in categorias_visibles.keys()]
    )

    async def select_callback(interaction_select: discord.Interaction):
        categoria = select.values[0]
        comandos = categorias_visibles[categoria]

        descripcion = "\n".join([f"**/{c.name}** → {c.description}" for c in comandos])

        embed = discord.Embed(
            title=f"📜 Comandos de {categoria}",
            description=descripcion,
            color=discord.Color.blurple()
        )
        await interaction_select.response.edit_message(embed=embed, view=view)

    select.callback = select_callback

    view = View()
    view.add_item(select)

    embed = discord.Embed(
        title="📜 Lista de Comandos",
        description="Selecciona una categoría para ver los comandos disponibles",
        color=discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



# ---------- /ship ----------
@bot.tree.command(name="ship", description="Calcula la compatibilidad entre dos personas.", extras={"categoria": "Información"})
@app_commands.describe(user1="Primera persona", user2="Segunda persona")
async def ship(interaction: discord.Interaction, user1: discord.User, user2: discord.User):
    score = random.randint(0, 100)
    bar = "█" * (score // 10) + "░" * (10 - score // 10)
    await interaction.response.send_message(
        f"❤️ Compatibilidad entre {user1.mention} y {user2.mention}: **{score}%**\n`[{bar}]`"
    )

# ---------- /calc ----------
@bot.tree.command(name="calc", description="Calculadora simple.", extras={"categoria": "Utilidad"})
@app_commands.describe(expression="Expresión matemática (ej. 2+2*3)")
async def calc(interaction: discord.Interaction, expression: str):
    try:
        result = eval(expression, {"__builtins__": None, "math": math}, {})
        await interaction.response.send_message(f"🧮 Resultado de `{expression}` = `{result}`")
    except:
        await interaction.response.send_message("❌ Expresión inválida.", ephemeral=True)

# ---------- /weather con embed ----------
@bot.tree.command(name="weather", description="Consulta el clima actual de una ciudad.", extras={"categoria": "Información"})
@app_commands.describe(city="Nombre de la ciudad")
async def weather(interaction: discord.Interaction, city: str):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

            if resp.status != 200 or "main" not in data:
                await interaction.response.send_message(f"⚠️ No se encontró la ciudad `{city}`.")
                return

            clima = data["weather"][0]["description"].capitalize()
            temp = data["main"]["temp"]
            sensacion = data["main"]["feels_like"]
            humedad = data["main"]["humidity"]
            icon_code = data["weather"][0]["icon"]
            icon_url = f"http://openweathermap.org/img/wn/{icon_code}@2x.png"

            embed = discord.Embed(
                title=f"Clima en {city.title()}",
                description=f"{clima}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=icon_url)
            embed.add_field(name="🌡️ Temperatura", value=f"{temp}°C", inline=True)
            embed.add_field(name="🥵 Sensación térmica", value=f"{sensacion}°C", inline=True)
            embed.add_field(name="💧 Humedad", value=f"{humedad}%", inline=True)

            await interaction.response.send_message(embed=embed)

# ------------------------------
# EJECUTAR BOT
# ------------------------------

keep_alive()

print(f"TOKEN leído: {os.getenv('TOKEN')[:5]}...")  # Para verificar que sí lee el token

try:
    bot.run(os.getenv("TOKEN"))
except Exception as e:
    print(f"❌ Error al iniciar el bot: {e}")