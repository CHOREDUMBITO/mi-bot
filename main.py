import discord
from discord import app_commands
from discord.ext import tasks
from flask import Flask
from threading import Thread
import os
import random
import json
import feedparser
from discord.ui import View, Select
from collections import defaultdict
from datetime import datetime, timedelta

# --- Mantener vivo el bot ---
app = Flask('')

@app.route('/')
def home():
    return "El bot está vivo!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Cliente principal ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# --- Canales y datos ---
CANAL_SUGERENCIAS = 1108242948879028334
CANAL_NIVELES = 1400694590327095378
CANAL_YOUTUBE = 1100279149236600882

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

# --- Sistema de economía ---
ECONOMIA_FILE = "economia.json"
if os.path.exists(ECONOMIA_FILE):
    with open(ECONOMIA_FILE, "r") as f:
        economia = json.load(f)
else:
    economia = {}

def guardar_economia():
    with open(ECONOMIA_FILE, "w") as f:
        json.dump(economia, f, indent=4)

def obtener_saldo(user_id):
    return economia.get(str(user_id), 0)

def añadir_saldo(user_id, cantidad):
    user_id = str(user_id)
    economia[user_id] = economia.get(user_id, 0) + cantidad
    guardar_economia()

def restar_saldo(user_id, cantidad):
    user_id = str(user_id)
    if economia.get(user_id, 0) >= cantidad:
        economia[user_id] -= cantidad
        guardar_economia()
        return True
    return False

# --- Cooldowns ---
cooldowns_work = {}
cooldowns_daily = {}

# --- Archivos de tienda e inventario ---
TIENDA_FILE = "tienda.json"
INVENTARIO_FILE = "inventario.json"
BANCO_FILE = "banco.json"

if os.path.exists(TIENDA_FILE):
    with open(TIENDA_FILE, "r") as f:
        tienda_items = json.load(f)
else:
    tienda_items = {
        "espada": {"precio": 500, "descripcion": "Una espada afilada."},
        "escudo": {"precio": 300, "descripcion": "Escudo resistente."},
        "pocion": {"precio": 150, "descripcion": "Recupera energía."}
    }
    with open(TIENDA_FILE, "w") as f:
        json.dump(tienda_items, f, indent=4)

if os.path.exists(INVENTARIO_FILE):
    with open(INVENTARIO_FILE, "r") as f:
        inventarios = json.load(f)
else:
    inventarios = {}

# --- Banco (ahora persistente) ---
if os.path.exists(BANCO_FILE):
    with open(BANCO_FILE, "r") as f:
        banco = json.load(f)
else:
    banco = {}

def guardar_tienda():
    with open(TIENDA_FILE, "w") as f:
        json.dump(tienda_items, f, indent=4)

def guardar_inventario():
    with open(INVENTARIO_FILE, "w") as f:
        json.dump(inventarios, f, indent=4)

def guardar_banco():
    with open(BANCO_FILE, "w") as f:
        json.dump(banco, f, indent=4)

def obtener_banco(user_id):
    return banco.get(str(user_id), 0)

def depositar_banco(user_id, cantidad):
    user_id = str(user_id)
    banco[user_id] = banco.get(user_id, 0) + cantidad
    guardar_banco()

def retirar_banco(user_id, cantidad):
    user_id = str(user_id)
    if banco.get(user_id, 0) >= cantidad:
        banco[user_id] -= cantidad
        guardar_banco()
        return True
    return False

# --- Sistema YouTube ---
YOUTUBE_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UC2OiC1E-tHN-IAO7RQINk_g"
ultimo_video_id = None

# ------------------------------
# EVENTOS
# ------------------------------
@bot.event
async def on_ready():
    await tree.sync()
    revisar_youtube.start()
    print(f"✅ Bot conectado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)

    # Sistema de niveles
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

    # Ganar monedas por mensaje
    añadir_saldo(user_id, random.randint(1, 5))

    await bot.process_commands(message)

# ------------------------------
# TAREA PARA REVISAR YOUTUBE
# ------------------------------
@tasks.loop(minutes=5)
async def revisar_youtube():
    global ultimo_video_id
    feed = feedparser.parse(YOUTUBE_FEED)
    if feed.entries:
        nuevo_video = feed.entries[0]
        video_id = nuevo_video.yt_videoid
        if ultimo_video_id != video_id:
            ultimo_video_id = video_id
            canal = bot.get_channel(CANAL_YOUTUBE)
            if canal:
                embed = discord.Embed(
                    title=nuevo_video.title,
                    url=nuevo_video.link,
                    description=getattr(nuevo_video, "media_description", "¡Nuevo video disponible!"),
                    color=discord.Color.red()
                )
                embed.set_author(name="🎥 ¡Nuevo video en el canal!")
                if hasattr(nuevo_video, "media_thumbnail"):
                    embed.set_thumbnail(url=nuevo_video.media_thumbnail[0]['url'])
                await canal.send(embed=embed)

# ------------------------------
# COMANDOS UTILIDAD / MODERACIÓN
# ------------------------------
@tree.command(name="sugerencia", description="Envía una sugerencia al servidor", extras={"categoria": "Utilidad"})
async def sugerencia(interaction: discord.Interaction, texto: str):
    if interaction.channel.id != CANAL_SUGERENCIAS:
        await interaction.response.send_message("❌ Solo en canal sugerencias.", ephemeral=True)
        return
    embed = discord.Embed(description=f"*{interaction.user.display_name}*: {texto}", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    await message.add_reaction("✅")
    await message.add_reaction("❌")

@tree.command(name="ping", description="Responde con Pong y el ping del bot", extras={"categoria": "Información"})
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latencia: {latency}ms")

@tree.command(name="clear", description="Borra mensajes recientes (admins)", extras={"categoria": "Moderación"})
@app_commands.describe(cantidad="Cantidad de mensajes a borrar (máximo 100)")
async def clear(interaction: discord.Interaction, cantidad: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Sin permisos.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=cantidad)
    await interaction.response.send_message(f"🧹 Borrados {len(deleted)} mensajes.", ephemeral=True)

# ------------------------------
# COMANDOS NIVELES
# ------------------------------
@tree.command(name="nivel", description="Muestra tu nivel y XP", extras={"categoria": "Utilidad"})
async def nivel(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    user_id = str(usuario.id)
    if user_id not in niveles:
        await interaction.response.send_message("❌ No tiene XP aún.", ephemeral=True)
        return
    xp = niveles[user_id]["xp"]
    nivel_actual = niveles[user_id]["nivel"]
    xp_necesario = nivel_actual * 100
    embed = discord.Embed(
        title=f"📊 Nivel de {usuario.display_name}",
        description=f"**Nivel:** {nivel_actual}\n**XP:** {xp}/{xp_necesario}",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)

@tree.command(name="toplevels", description="Top jugadores por nivel", extras={"categoria": "Utilidad"})
async def toplevels(interaction: discord.Interaction):
    if not niveles:
        await interaction.response.send_message("❌ Aún no hay datos.", ephemeral=True)
        return
    top = sorted(niveles.items(), key=lambda x: (x[1]["nivel"], x[1]["xp"]), reverse=True)[:10]
    descripcion = ""
    for i, (user_id, datos) in enumerate(top, start=1):
        usuario = await bot.fetch_user(int(user_id))
        descripcion += f"**#{i}** {usuario.display_name} → Nivel {datos['nivel']} ({datos['xp']} XP)\n"
    embed = discord.Embed(title="🏆 Top Niveles", description=descripcion, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ------------------------------
# COMANDOS ECONOMÍA
# ------------------------------
@tree.command(name="balance", description="Muestra tu saldo", extras={"categoria": "Economía"})
async def balance(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    total = obtener_saldo(usuario.id) + obtener_banco(usuario.id)
    await interaction.response.send_message(
        f"💰 {usuario.display_name} tiene {total} monedas (💵 {obtener_saldo(usuario.id)} | 🏦 {obtener_banco(usuario.id)})",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="work", description="Trabaja y gana monedas (1h cooldown)", extras={"categoria": "Economía"})
async def work(interaction: discord.Interaction):
    user_id = interaction.user.id
    ahora = datetime.utcnow()
    if user_id in cooldowns_work and ahora - cooldowns_work[user_id] < timedelta(hours=1):
        espera = timedelta(hours=1) - (ahora - cooldowns_work[user_id])
        await interaction.response.send_message(
            f"⏳ Espera {espera.seconds//60}m para volver a trabajar.",
            ephemeral=True  # Cambiado a ephemeral
        )
        return
    ganancias = random.randint(50, 150)
    añadir_saldo(user_id, ganancias)
    cooldowns_work[user_id] = ahora
    await interaction.response.send_message(
        f"💼 Ganaste {ganancias} monedas trabajando.",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="daily", description="Reclama tu recompensa diaria", extras={"categoria": "Economía"})
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    ahora = datetime.utcnow()
    if user_id in cooldowns_daily and ahora - cooldowns_daily[user_id] < timedelta(hours=24):
        espera = timedelta(hours=24) - (ahora - cooldowns_daily[user_id])
        await interaction.response.send_message(
            f"⏳ Espera {espera.seconds//3600}h para volver a reclamar.",
            ephemeral=True  # Cambiado a ephemeral
        )
        return
    recompensa = random.randint(100, 300)
    añadir_saldo(user_id, recompensa)
    cooldowns_daily[user_id] = ahora
    await interaction.response.send_message(
        f"🎁 Reclamaste {recompensa} monedas diarias.",
        ephemeral=True  # Cambiado a ephemeral
    )

# --- Banco ---
@tree.command(name="bank", description="Saldo en el banco", extras={"categoria": "Economía"})
async def bank(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏦 Saldo en banco: {obtener_banco(interaction.user.id)} monedas.",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="deposit", description="Deposita en el banco", extras={"categoria": "Economía"})
async def deposit(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        return
    if not restar_saldo(interaction.user.id, cantidad):
        await interaction.response.send_message("❌ No tienes suficiente dinero.", ephemeral=True)
        return
    depositar_banco(interaction.user.id, cantidad)
    await interaction.response.send_message(
        f"🏦 Depositaste {cantidad} monedas.",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="withdraw", description="Retira del banco", extras={"categoria": "Economía"})
async def withdraw(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        return
    if not retirar_banco(interaction.user.id, cantidad):
        await interaction.response.send_message("❌ No tienes suficiente en el banco.", ephemeral=True)
        return
    añadir_saldo(interaction.user.id, cantidad)
    await interaction.response.send_message(
        f"🏦 Retiraste {cantidad} monedas.",
        ephemeral=True  # Cambiado a ephemeral
    )

# --- Transferencias ---
@tree.command(name="pay", description="Paga a otro usuario", extras={"categoria": "Economía"})
async def pay(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        return
    if usuario.id == interaction.user.id:
        await interaction.response.send_message("❌ No puedes pagarte a ti mismo.", ephemeral=True)
        return
    if not restar_saldo(interaction.user.id, cantidad):
        await interaction.response.send_message("❌ No tienes suficiente dinero.", ephemeral=True)
        return
    añadir_saldo(usuario.id, cantidad)
    await interaction.response.send_message(
        f"💸 Has pagado {cantidad} monedas a {usuario.display_name}.",
        ephemeral=True  # Cambiado a ephemeral
    )

# --- Tienda ---
@tree.command(name="shop", description="Ver tienda", extras={"categoria": "Economía"})
async def shop(interaction: discord.Interaction):
    if not tienda_items:
        await interaction.response.send_message("🛒 La tienda está vacía.", ephemeral=True)
        return
    desc = "\n".join([f"**{n.capitalize()}** - {d['precio']} monedas\n_{d['descripcion']}_" for n, d in tienda_items.items()])
    embed = discord.Embed(title="🛒 Tienda", description=desc, color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)  # Cambiado a ephemeral

@tree.command(name="buy", description="Compra un artículo", extras={"categoria": "Economía"})
async def buy(interaction: discord.Interaction, articulo: str):
    articulo = articulo.lower()
    if articulo not in tienda_items:
        await interaction.response.send_message("❌ No está en la tienda.", ephemeral=True)
        return
    precio = tienda_items[articulo]["precio"]
    if not restar_saldo(interaction.user.id, precio):
        await interaction.response.send_message("❌ No tienes suficiente dinero.", ephemeral=True)
        return
    uid = str(interaction.user.id)
    inventarios.setdefault(uid, {})
    inventarios[uid][articulo] = inventarios[uid].get(articulo, 0) + 1
    guardar_inventario()
    await interaction.response.send_message(
        f"✅ Compraste {articulo} por {precio} monedas.",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="sell", description="Vende un artículo (50% valor)", extras={"categoria": "Economía"})
async def sell(interaction: discord.Interaction, articulo: str):
    articulo = articulo.lower()
    uid = str(interaction.user.id)
    if uid not in inventarios or articulo not in inventarios[uid] or inventarios[uid][articulo] <= 0:
        await interaction.response.send_message("❌ No tienes ese artículo.", ephemeral=True)
        return
    if articulo not in tienda_items:
        await interaction.response.send_message("❌ Ese artículo ya no existe en la tienda.", ephemeral=True)
        return
    precio = tienda_items[articulo]["precio"] // 2
    inventarios[uid][articulo] -= 1
    if inventarios[uid][articulo] == 0:
        del inventarios[uid][articulo]
    guardar_inventario()
    añadir_saldo(uid, precio)
    await interaction.response.send_message(
        f"💰 Vendiste {articulo} por {precio} monedas.",
        ephemeral=True  # Cambiado a ephemeral
    )

@tree.command(name="inventory", description="Ver inventario", extras={"categoria": "Economía"})
async def inventory(interaction: discord.Interaction, usuario: discord.Member = None):
    usuario = usuario or interaction.user
    uid = str(usuario.id)
    if uid not in inventarios or not inventarios[uid]:
        await interaction.response.send_message(f"📦 {usuario.display_name} no tiene artículos.", ephemeral=True)
        return
    desc = "\n".join([f"**{i.capitalize()}** x{c}" for i, c in inventarios[uid].items()])
    embed = discord.Embed(title=f"📦 Inventario de {usuario.display_name}", description=desc, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)  # Cambiado a ephemeral

# --- Comandos admin para modificar tienda ---
@tree.command(name="additem", description="Añadir artículo a tienda (admin)", extras={"categoria": "Economía"})
@app_commands.checks.has_permissions(administrator=True)
async def additem(interaction: discord.Interaction, nombre: str, precio: int, descripcion: str):
    nombre = nombre.lower()
    tienda_items[nombre] = {"precio": precio, "descripcion": descripcion}
    guardar_tienda()
    await interaction.response.send_message(f"✅ Añadido {nombre} a la tienda.", ephemeral=True)  # Cambiado a ephemeral

@tree.command(name="removeitem", description="Quitar artículo de tienda (admin)", extras={"categoria": "Economía"})
@app_commands.checks.has_permissions(administrator=True)
async def removeitem(interaction: discord.Interaction, nombre: str):
    nombre = nombre.lower()
    if nombre not in tienda_items:
        await interaction.response.send_message("❌ No existe en la tienda.", ephemeral=True)
        return
    del tienda_items[nombre]
    guardar_tienda()
    await interaction.response.send_message(f"✅ Eliminado {nombre} de la tienda.", ephemeral=True)  # Cambiado a ephemeral

# --- Comando para apostar ---
@tree.command(name="bet", description="Apuesta una cantidad", extras={"categoria": "Economía"})
async def bet(interaction: discord.Interaction, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("❌ Cantidad inválida.", ephemeral=True)
        return
    if obtener_saldo(interaction.user.id) < cantidad:
        await interaction.response.send_message("❌ No tienes suficiente dinero para apostar.", ephemeral=True)
        return
    resultado = random.choice(["ganar", "perder"])
    if resultado == "ganar":
        añadir_saldo(interaction.user.id, cantidad)
        await interaction.response.send_message(f"🎉 ¡Ganaste {cantidad} monedas!", ephemeral=True)  # Cambiado a ephemeral
    else:
        restar_saldo(interaction.user.id, cantidad)
        await interaction.response.send_message(f"😞 Perdiste {cantidad} monedas.", ephemeral=True)  # Cambiado a ephemeral

# --- Comando Top dinero (público) ---
@tree.command(name="topmoney", description="Top usuarios con más dinero", extras={"categoria": "Economía"})
async def topmoney(interaction: discord.Interaction):
    if not economia:
        await interaction.response.send_message("❌ No hay datos aún.")
        return
    top = sorted(economia.items(), key=lambda x: x[1], reverse=True)[:10]
    descripcion = ""
    for i, (user_id, dinero) in enumerate(top, start=1):
        try:
            usuario = await bot.fetch_user(int(user_id))
            nombre = usuario.display_name
        except:
            nombre = f"Usuario {user_id}"
        descripcion += f"**#{i}** {nombre} → {dinero} monedas\n"
    embed = discord.Embed(title="💰 Top Dinero", description=descripcion, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ------------------------------
# EJECUTAR EL BOT
# ------------------------------
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN")
    bot.run(TOKEN)
