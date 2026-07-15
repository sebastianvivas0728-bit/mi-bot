require('dotenv').config();
const {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  SlashCommandBuilder,
  ChannelType,
  PermissionFlagsBits,
  ModalBuilder,
  TextInputBuilder,
  TextInputStyle,
  ActionRowBuilder,
  EmbedBuilder,
  version: discordJsVersion,
} = require('discord.js');

const client = new Client({
  intents: [GatewayIntentBits.Guilds],
});

const COLOR_POR_DEFECTO = 0xF5C451; // Color por defecto de la barra lateral de /anuncio
const MAX_MINUTOS_MUTE = 40320; // 28 días, límite de Discord para timeouts

// ============================================================
// 1. DEFINICIÓN DE LOS COMANDOS (slash commands)
// ============================================================

const commands = [
  new SlashCommandBuilder()
    .setName('anuncio')
    .setDescription('Publica un anuncio con formato en el canal que elijas')
    .addChannelOption(option =>
      option
        .setName('canal')
        .setDescription('Canal donde se enviará el anuncio')
        .addChannelTypes(ChannelType.GuildText, ChannelType.GuildAnnouncement)
        .setRequired(true)
    )
    .addStringOption(option =>
      option
        .setName('color')
        .setDescription('Color de la barra lateral (hex, ej: #f5c451)')
        .setRequired(false)
    )
    .addRoleOption(option =>
      option
        .setName('mencionar')
        .setDescription('Rol a mencionar junto con el anuncio (opcional)')
        .setRequired(false)
    )
    .setDefaultMemberPermissions(PermissionFlagsBits.ManageMessages),

  new SlashCommandBuilder()
    .setName('userinfo')
    .setDescription('Muestra información de un usuario del servidor')
    .addUserOption(option =>
      option
        .setName('usuario')
        .setDescription('Usuario a consultar (por defecto, tú mismo)')
        .setRequired(false)
    ),

  new SlashCommandBuilder()
    .setName('botinfo')
    .setDescription('Muestra información y estadísticas del bot'),

  new SlashCommandBuilder()
    .setName('ban')
    .setDescription('Banea a un usuario del servidor')
    .addUserOption(option =>
      option.setName('usuario').setDescription('Usuario a banear').setRequired(true)
    )
    .addStringOption(option =>
      option.setName('razon').setDescription('Razón del baneo').setRequired(false)
    )
    .addIntegerOption(option =>
      option
        .setName('borrar_mensajes')
        .setDescription('Días de mensajes a borrar (0-7). Por defecto 0.')
        .setMinValue(0)
        .setMaxValue(7)
        .setRequired(false)
    )
    .setDefaultMemberPermissions(PermissionFlagsBits.BanMembers),

  new SlashCommandBuilder()
    .setName('mute')
    .setDescription('Silencia temporalmente a un usuario (timeout)')
    .addUserOption(option =>
      option.setName('usuario').setDescription('Usuario a silenciar').setRequired(true)
    )
    .addIntegerOption(option =>
      option
        .setName('minutos')
        .setDescription('Duración en minutos (máx. 40320 = 28 días). Por defecto 10.')
        .setMinValue(1)
        .setMaxValue(MAX_MINUTOS_MUTE)
        .setRequired(false)
    )
    .addStringOption(option =>
      option.setName('razon').setDescription('Razón del silencio').setRequired(false)
    )
    .setDefaultMemberPermissions(PermissionFlagsBits.ModerateMembers),
].map(command => command.toJSON());

// ============================================================
// 2. REGISTRO AUTOMÁTICO DE LOS COMANDOS AL INICIAR
// ============================================================

async function registrarComandos() {
  const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
  try {
    console.log(`Registrando ${commands.length} comando(s)...`);
    if (process.env.GUILD_ID) {
      await rest.put(
        Routes.applicationGuildCommands(process.env.CLIENT_ID, process.env.GUILD_ID),
        { body: commands }
      );
      console.log('Comandos registrados en el servidor indicado (GUILD_ID).');
    } else {
      await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body: commands });
      console.log('Comandos registrados globalmente (puede tardar hasta 1 hora en aparecer).');
    }
  } catch (error) {
    console.error('Error registrando comandos:', error);
  }
}

// ============================================================
// 3. FUNCIONES AUXILIARES
// ============================================================

function formatearDuracion(ms) {
  const segundos = Math.floor(ms / 1000) % 60;
  const minutos = Math.floor(ms / (1000 * 60)) % 60;
  const horas = Math.floor(ms / (1000 * 60 * 60)) % 24;
  const dias = Math.floor(ms / (1000 * 60 * 60 * 24));
  return `${dias}d ${horas}h ${minutos}m ${segundos}s`;
}

// ============================================================
// 4. MANEJO DE INTERACCIONES
// ============================================================

client.once('ready', async () => {
  console.log(`Bot conectado como ${client.user.tag}`);
  await registrarComandos();
});

client.on('interactionCreate', async (interaction) => {
  try {
    // ---------- /anuncio: abre el modal ----------
    if (interaction.isChatInputCommand() && interaction.commandName === 'anuncio') {
      const canal = interaction.options.getChannel('canal');
      const colorInput = interaction.options.getString('color') || '';
      const rolMencion = interaction.options.getRole('mencionar');

      const permisosBot = canal.permissionsFor(interaction.guild.members.me);
      if (!permisosBot?.has(PermissionFlagsBits.SendMessages) || !permisosBot?.has(PermissionFlagsBits.EmbedLinks)) {
        return interaction.reply({
          content: `No tengo permisos para enviar mensajes o embeds en ${canal}.`,
          ephemeral: true,
        });
      }

      const customId = `anuncioModal|${canal.id}|${encodeURIComponent(colorInput)}|${rolMencion ? rolMencion.id : ''}`;

      const modal = new ModalBuilder().setCustomId(customId).setTitle('Crear anuncio');

      const tituloInput = new TextInputBuilder()
        .setCustomId('titulo')
        .setLabel('Título del anuncio')
        .setStyle(TextInputStyle.Short)
        .setPlaceholder('Ej: NYC | DRILL ROLEPLAY 🇺🇸')
        .setMaxLength(256)
        .setRequired(true);

      const contenidoInput = new TextInputBuilder()
        .setCustomId('contenido')
        .setLabel('Contenido (usa saltos de línea y -)')
        .setStyle(TextInputStyle.Paragraph)
        .setPlaceholder('1. Respeto al Roleplay\n- Todas las acciones deben tener sentido dentro del rol.')
        .setMaxLength(4000)
        .setRequired(true);

      modal.addComponents(
        new ActionRowBuilder().addComponents(tituloInput),
        new ActionRowBuilder().addComponents(contenidoInput)
      );

      return interaction.showModal(modal);
    }

    // ---------- Envío del modal de /anuncio ----------
    if (interaction.isModalSubmit() && interaction.customId.startsWith('anuncioModal|')) {
      const [, canalId, colorEncoded, rolId] = interaction.customId.split('|');
      const colorInput = decodeURIComponent(colorEncoded);

      const titulo = interaction.fields.getTextInputValue('titulo');
      const contenido = interaction.fields.getTextInputValue('contenido');

      const canal = await interaction.guild.channels.fetch(canalId).catch(() => null);
      if (!canal) {
        return interaction.reply({ content: 'No se encontró el canal indicado.', ephemeral: true });
      }

      let color = COLOR_POR_DEFECTO;
      if (/^#?[0-9a-fA-F]{6}$/.test(colorInput)) {
        color = parseInt(colorInput.replace('#', ''), 16);
      }

      const embed = new EmbedBuilder()
        .setColor(color)
        .setTitle(titulo)
        .setDescription(contenido)
        .setTimestamp()
        .setFooter({ text: interaction.guild.name, iconURL: interaction.guild.iconURL() || undefined });

      const contenidoMencion = rolId ? `<@&${rolId}>` : undefined;

      await canal.send({ content: contenidoMencion, embeds: [embed] });
      return interaction.reply({ content: `Anuncio publicado en ${canal}.`, ephemeral: true });
    }

    if (!interaction.isChatInputCommand()) return;

    // ---------- /userinfo ----------
    if (interaction.commandName === 'userinfo') {
      const usuario = interaction.options.getUser('usuario') || interaction.user;
      const miembro = await interaction.guild.members.fetch(usuario.id).catch(() => null);

      const roles = miembro
        ? miembro.roles.cache
            .filter(rol => rol.id !== interaction.guild.id)
            .sort((a, b) => b.position - a.position)
            .map(rol => `<@&${rol.id}>`)
        : [];

      const embed = new EmbedBuilder()
        .setColor(miembro?.displayHexColor && miembro.displayHexColor !== '#000000' ? miembro.displayHexColor : 0x5865F2)
        .setTitle(`Información de ${usuario.username}`)
        .setThumbnail(usuario.displayAvatarURL({ size: 256 }))
        .addFields(
          { name: 'Usuario', value: `<@${usuario.id}>`, inline: true },
          { name: 'ID', value: usuario.id, inline: true },
          { name: 'Cuenta creada', value: `<t:${Math.floor(usuario.createdTimestamp / 1000)}:F>`, inline: false }
        )
        .setTimestamp();

      if (miembro) {
        embed.addFields(
          { name: 'Se unió al servidor', value: `<t:${Math.floor(miembro.joinedTimestamp / 1000)}:F>`, inline: false },
          { name: `Roles (${roles.length})`, value: roles.length ? roles.join(' ') : 'Sin roles', inline: false }
        );
      } else {
        embed.addFields({ name: 'Nota', value: 'Este usuario no se encuentra en el servidor.' });
      }

      return interaction.reply({ embeds: [embed] });
    }

    // ---------- /botinfo ----------
    if (interaction.commandName === 'botinfo') {
      const uptime = formatearDuracion(client.uptime);
      const servidores = client.guilds.cache.size;
      const usuarios = client.guilds.cache.reduce((total, guild) => total + guild.memberCount, 0);
      const ping = client.ws.ping;

      const embed = new EmbedBuilder()
        .setColor(0x5865F2)
        .setTitle(`${client.user.username} — Información del bot`)
        .setThumbnail(client.user.displayAvatarURL({ size: 256 }))
        .addFields(
          { name: 'Servidores', value: `${servidores}`, inline: true },
          { name: 'Usuarios (aprox.)', value: `${usuarios}`, inline: true },
          { name: 'Ping', value: `${ping}ms`, inline: true },
          { name: 'Tiempo en línea', value: uptime, inline: true },
          { name: 'Librería', value: `discord.js v${discordJsVersion}`, inline: true },
          { name: 'Node.js', value: process.version, inline: true }
        )
        .setFooter({ text: 'NYC | DRILL ROLEPLAY 🇺🇸' })
        .setTimestamp();

      return interaction.reply({ embeds: [embed] });
    }

    // ---------- /ban ----------
    if (interaction.commandName === 'ban') {
      const usuario = interaction.options.getUser('usuario', true);
      const razon = interaction.options.getString('razon') || 'No se proporcionó una razón';
      const diasBorrado = interaction.options.getInteger('borrar_mensajes') || 0;

      if (usuario.id === interaction.user.id) {
        return interaction.reply({ content: 'No puedes banearte a ti mismo.', ephemeral: true });
      }
      if (usuario.id === interaction.guild.ownerId) {
        return interaction.reply({ content: 'No puedes banear al dueño del servidor.', ephemeral: true });
      }

      const miembro = await interaction.guild.members.fetch(usuario.id).catch(() => null);
      if (miembro) {
        if (!miembro.bannable) {
          return interaction.reply({
            content: 'No puedo banear a este usuario (su rol es igual o superior al mío).',
            ephemeral: true,
          });
        }
        const autorMiembro = await interaction.guild.members.fetch(interaction.user.id);
        if (
          miembro.roles.highest.position >= autorMiembro.roles.highest.position &&
          interaction.guild.ownerId !== interaction.user.id
        ) {
          return interaction.reply({
            content: 'No puedes banear a alguien con un rol igual o superior al tuyo.',
            ephemeral: true,
          });
        }
      }

      try {
        await interaction.guild.members.ban(usuario.id, {
          reason: `${razon} | Baneado por ${interaction.user.tag}`,
          deleteMessageSeconds: diasBorrado * 24 * 60 * 60,
        });

        const embed = new EmbedBuilder()
          .setColor(0xED4245)
          .setTitle('Usuario baneado')
          .addFields(
            { name: 'Usuario', value: `${usuario.tag} (${usuario.id})`, inline: false },
            { name: 'Razón', value: razon, inline: false },
            { name: 'Moderador', value: `<@${interaction.user.id}>`, inline: false }
          )
          .setTimestamp();

        return interaction.reply({ embeds: [embed] });
      } catch (error) {
        console.error(error);
        return interaction.reply({ content: 'Ocurrió un error al intentar banear al usuario.', ephemeral: true });
      }
    }

    // ---------- /mute ----------
    if (interaction.commandName === 'mute') {
      const usuario = interaction.options.getUser('usuario', true);
      const minutos = interaction.options.getInteger('minutos') || 10;
      const razon = interaction.options.getString('razon') || 'No se proporcionó una razón';

      if (usuario.id === interaction.user.id) {
        return interaction.reply({ content: 'No puedes silenciarte a ti mismo.', ephemeral: true });
      }
      if (usuario.id === interaction.guild.ownerId) {
        return interaction.reply({ content: 'No puedes silenciar al dueño del servidor.', ephemeral: true });
      }

      const miembro = await interaction.guild.members.fetch(usuario.id).catch(() => null);
      if (!miembro) {
        return interaction.reply({ content: 'Ese usuario no está en el servidor.', ephemeral: true });
      }
      if (!miembro.moderatable) {
        return interaction.reply({
          content: 'No puedo silenciar a este usuario (su rol es igual o superior al mío).',
          ephemeral: true,
        });
      }

      const autorMiembro = await interaction.guild.members.fetch(interaction.user.id);
      if (
        miembro.roles.highest.position >= autorMiembro.roles.highest.position &&
        interaction.guild.ownerId !== interaction.user.id
      ) {
        return interaction.reply({
          content: 'No puedes silenciar a alguien con un rol igual o superior al tuyo.',
          ephemeral: true,
        });
      }

      try {
        await miembro.timeout(minutos * 60 * 1000, `${razon} | Silenciado por ${interaction.user.tag}`);

        const embed = new EmbedBuilder()
          .setColor(0xFEE75C)
          .setTitle('Usuario silenciado')
          .addFields(
            { name: 'Usuario', value: `${usuario.tag} (${usuario.id})`, inline: false },
            { name: 'Duración', value: `${minutos} minuto(s)`, inline: true },
            { name: 'Razón', value: razon, inline: false },
            { name: 'Moderador', value: `<@${interaction.user.id}>`, inline: false }
          )
          .setTimestamp();

        return interaction.reply({ embeds: [embed] });
      } catch (error) {
        console.error(error);
        return interaction.reply({ content: 'Ocurrió un error al intentar silenciar al usuario.', ephemeral: true });
      }
    }
  } catch (error) {
    console.error(error);
    if (interaction.isRepliable()) {
      await interaction.reply({ content: 'Ocurrió un error al procesar la interacción.', ephemeral: true }).catch(() => {});
    }
  }
});

client.login(process.env.DISCORD_TOKEN);
