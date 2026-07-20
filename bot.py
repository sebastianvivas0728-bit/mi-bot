import discord
from discord import app_commands
import json
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ── Sistema de idiomas ─────────────────────────────────────
idioma_servidor = {}

TEXTOS = {
    "es": {
        "reglas_ok": "✅ Mensaje enviado en {canal}",
        "kick_ok": "👢 **{usuario}** fue expulsado. Razón: {razon}",
        "kick_rol_alto": "❌ No puedo expulsar a ese usuario (su rol es igual o superior al mío).",
        "kick_sin_permisos": "❌ No tengo permisos suficientes para expulsar a ese usuario.",
        "xp_ok": "✨ **{usuario}** ahora tiene **{total}** XP ({signo}{cantidad}).",
        "nivel_ok": "📊 **{usuario}** tiene **{xp}** XP.",
        "sin_permiso": "❌ No tienes permisos para usar este comando.",
    },
    "en": {
        "reglas_ok": "✅ Message sent in {canal}",
        "kick_ok": "👢 **{usuario}** was kicked. Reason: {razon}",
        "kick_rol_alto": "❌ I can't kick that user (their role is equal to or higher than mine).",
        "kick_sin_permisos": "❌ I don't have enough permissions to kick that user.",
        "xp_ok": "✨ **{usuario}** now has **{total}** XP ({signo}{cantidad}).",
        "nivel_ok": "📊 **{usuario}** has **{xp}** XP.",
        "sin_permiso": "❌ You don't have permission to use this command.",
    },
    "pt": {
        "reglas_ok": "✅ Mensagem enviada em {canal}",
        "kick_ok": "👢 **{usuario}** foi expulso. Motivo: {razon}",
        "kick_rol_alto": "❌ Não posso expulsar esse usuário (o cargo dele é igual ou superior ao meu).",
        "kick_sin_permisos": "❌ Não tenho permissões suficientes para expulsar esse usuário.",
        "xp_ok": "✨ **{usuario}** agora tem **{total}** XP ({signo}{cantidad}).",
        "nivel_ok": "📊 **{usuario}** tem **{xp}** XP.",
        "sin_permiso": "❌ Você não tem permissão para usar este comando.",
    },
}


def t(guild_id, clave, **kwargs):
    lang = idioma_servidor.get(guild_id, "es")
    texto = TEXTOS[lang].get(clave, TEXTOS["es"].get(clave, clave))
    return texto.format(**kwargs) if kwargs else texto


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot conectado como: {client.user}")
    await client.change_presence(activity=discord.Game(name="/reglas /kick /xp"))


# ── XP: almacenamiento en JSON ──────────────────────────────
XP_FILE = "xp_data.json"


def cargar_xp() -> dict:
    if not os.path.exists(XP_FILE):
        return {}
    with open(XP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def guardar_xp(data: dict) -> None:
    with open(XP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── /reglas ──────────────────────────────────────────────────
@tree.command(name="reglas", description="Envía un mensaje/reglas a un canal elegido")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    canal="Canal donde se enviará el mensaje",
    texto="El texto que quieres que aparezca en el mensaje",
)
async def reglas(interaction: discord.Interaction, canal: discord.TextChannel, texto: str):
    gid = interaction.guild.id
    embed = discord.Embed(
        title="📋 『SERVER RULES』",
        description=texto,
        color=discord.Color.blurple(),
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    await canal.send(embed=embed)
    await interaction.response.send_message(t(gid, "reglas_ok", canal=canal.mention), ephemeral=True)


# ── /kick ────────────────────────────────────────────────────
@tree.command(name="kick", description="Expulsa a un usuario del servidor")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(
    usuario="Usuario que quieres expulsar",
    razon="Motivo de la expulsión (opcional)",
)
async def kick(interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin razón especificada"):
    gid = interaction.guild.id

    if usuario.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message(t(gid, "kick_rol_alto"), ephemeral=True)
        return

    try:
        await usuario.kick(reason=razon)
        await interaction.response.send_message(t(gid, "kick_ok", usuario=usuario, razon=razon))
    except discord.Forbidden:
        await interaction.response.send_message(t(gid, "kick_sin_permisos"), ephemeral=True)


# ── /xp ──────────────────────────────────────────────────────
@tree.command(name="xp", description="Da (o quita) XP a un usuario")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    usuario="Usuario al que le darás XP",
    cantidad="Cantidad de XP a otorgar (usa un número negativo para quitar)",
)
async def xp(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    gid = interaction.guild.id
    data = cargar_xp()
    user_id = str(usuario.id)
    data[user_id] = max(0, data.get(user_id, 0) + cantidad)
    guardar_xp(data)

    signo = "+" if cantidad >= 0 else ""
    await interaction.response.send_message(
        t(gid, "xp_ok", usuario=usuario, total=data[user_id], signo=signo, cantidad=cantidad)
    )


# ── /nivel (consultar XP) ───────────────────────────────────
@tree.command(name="nivel", description="Muestra el XP de un usuario")
@app_commands.describe(usuario="Usuario a consultar (por defecto, tú mismo)")
async def nivel(interaction: discord.Interaction, usuario: discord.Member = None):
    gid = interaction.guild.id
    usuario = usuario or interaction.user
    data = cargar_xp()
    xp_actual = data.get(str(usuario.id), 0)
    await interaction.response.send_message(t(gid, "nivel_ok", usuario=usuario, xp=xp_actual))


# ── Manejo de errores de permisos (para todos los comandos) ─
@reglas.error
@kick.error
@xp.error
async def comandos_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(t(interaction.guild.id, "sin_permiso"), ephemeral=True)
    else:
        raise error

# client.run(os.getenv("DISCORD_TOKEN"))  # usa variable de entorno, no pongas el token aquí
