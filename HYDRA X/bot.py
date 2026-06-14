"""
HydraX — a lightweight Discord music bot.

Plays from YouTube, SoundCloud, and Spotify (Spotify requires a Lavalink node
with the LavaSrc plugin). Built on discord.py and wavelink, backed by a public
Lavalink v4 node. Single-file by design for simple hosting.

Developed by Rajnikant.
"""

from __future__ import annotations

import logging
import os

import discord
import wavelink
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("hydrax")


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
class Settings:
    """Runtime configuration sourced from environment variables."""

    token: str = os.getenv("DISCORD_TOKEN", "")
    guild_id: int | None = int(g) if (g := os.getenv("GUILD_ID", "").strip()) else None

    lavalink_host: str = os.getenv("LAVALINK_HOST", "lavalink.jirayu.net")
    lavalink_port: int = int(os.getenv("LAVALINK_PORT", "443"))
    lavalink_pass: str = os.getenv("LAVALINK_PASS", "youshallnotpass")
    lavalink_secure: bool = os.getenv("LAVALINK_SECURE", "true").lower() == "true"

    @classmethod
    def node_uri(cls) -> str:
        scheme = "https" if cls.lavalink_secure else "http"
        return f"{scheme}://{cls.lavalink_host}:{cls.lavalink_port}"


# --------------------------------------------------------------------------- #
# Presentation helpers
# --------------------------------------------------------------------------- #
def format_duration(milliseconds: int) -> str:
    """Render a track length in milliseconds as m:ss."""
    seconds = milliseconds // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def now_playing_embed(track: wavelink.Playable) -> discord.Embed:
    """Build the embed shown for the currently playing track."""
    embed = discord.Embed(
        title="Now Playing",
        description=f"**[{track.title}]({track.uri})**",
        colour=discord.Colour.purple(),
    )
    if track.author:
        embed.add_field(name="Artist", value=track.author, inline=True)
    if track.length:
        embed.add_field(name="Duration", value=format_duration(track.length), inline=True)
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    embed.set_footer(text="HydraX • Developed by Rajnikant")
    return embed


# --------------------------------------------------------------------------- #
# Interactive playback controls
# --------------------------------------------------------------------------- #
class PlayerControls(discord.ui.View):
    """A row of buttons attached to the Now Playing message."""

    def __init__(self, player: wavelink.Player) -> None:
        super().__init__(timeout=None)
        self.player = player

    async def _ack(self, interaction: discord.Interaction, message: str) -> None:
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def toggle_pause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.player.pause(not self.player.paused)
        await self._ack(interaction, "Paused." if self.player.paused else "Resumed.")

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.player.skip(force=True)
        await self._ack(interaction, "Skipped.")

    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.player.queue.shuffle()
        await self._ack(interaction, "Queue shuffled.")

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def cycle_loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        transitions = {
            wavelink.QueueMode.normal: (wavelink.QueueMode.loop, "Looping the current track."),
            wavelink.QueueMode.loop: (wavelink.QueueMode.loop_all, "Looping the queue."),
            wavelink.QueueMode.loop_all: (wavelink.QueueMode.normal, "Loop disabled."),
        }
        self.player.queue.mode, message = transitions[self.player.queue.mode]
        await self._ack(interaction, message)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.player.queue.clear()
        await self.player.disconnect()
        await self._ack(interaction, "Stopped playback and left the channel.")


# --------------------------------------------------------------------------- #
# Bot
# --------------------------------------------------------------------------- #
class HydraX(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self) -> None:
        node = wavelink.Node(uri=Settings.node_uri(), password=Settings.lavalink_pass)
        await wavelink.Pool.connect(nodes=[node], client=self)
        await self._sync_commands()

    async def _sync_commands(self) -> None:
        if Settings.guild_id:
            guild = discord.Object(id=Settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild %s.", Settings.guild_id)
        else:
            await self.tree.sync()
            logger.info("Slash commands synced globally (may take up to an hour).")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (id: %s).", self.user, self.user.id)

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logger.info("Lavalink node %s is ready.", payload.node.identifier)

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        # wavelink advances the queue on its own; we only announce the new track.
        player = payload.player
        channel = getattr(player, "home_channel", None) if player else None
        if channel:
            await channel.send(embed=now_playing_embed(payload.track), view=PlayerControls(player))


bot = HydraX()


async def resolve_player(interaction: discord.Interaction, *, require_track: bool = False) -> wavelink.Player | None:
    """
    Return the guild's active player, or reply with an error and return None.

    Set require_track=True to also require that a track is currently playing.
    """
    player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
    if player is None:
        await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
        return None
    if require_track and not player.playing:
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return None
    return player


# --------------------------------------------------------------------------- #
# Playback commands
# --------------------------------------------------------------------------- #
@bot.tree.command(description="Play a track or playlist from YouTube, Spotify, or SoundCloud.")
@app_commands.describe(query="A search term or a link.")
async def play(interaction: discord.Interaction, query: str) -> None:
    voice = interaction.user.voice
    if not voice or not voice.channel:
        await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
        return

    await interaction.response.defer()

    player: wavelink.Player | None = interaction.guild.voice_client  # type: ignore[assignment]
    if player is None:
        player = await voice.channel.connect(cls=wavelink.Player)
    player.home_channel = interaction.channel

    results = await wavelink.Playable.search(query)
    if not results:
        await interaction.followup.send("No results found.")
        return

    if isinstance(results, wavelink.Playlist):
        count = await player.queue.put_wait(results)
        await interaction.followup.send(f"Queued **{count}** tracks from **{results.name}**.")
    else:
        track = results[0]
        await player.queue.put_wait(track)
        await interaction.followup.send(f"Queued **{track.title}**.")

    if not player.playing:
        await player.play(player.queue.get())


@bot.tree.command(description="Skip the current track.")
async def skip(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction, require_track=True):
        await player.skip(force=True)
        await interaction.response.send_message("Skipped.")


@bot.tree.command(description="Pause playback.")
async def pause(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction, require_track=True):
        await player.pause(True)
        await interaction.response.send_message("Paused.")


@bot.tree.command(description="Resume playback.")
async def resume(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction):
        await player.pause(False)
        await interaction.response.send_message("Resumed.")


@bot.tree.command(description="Stop playback and leave the voice channel.")
async def stop(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction):
        player.queue.clear()
        await player.disconnect()
        await interaction.response.send_message("Stopped and left the channel.")


@bot.tree.command(description="Set the playback volume (0–100).")
@app_commands.describe(level="Volume from 0 to 100.")
async def volume(interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]) -> None:
    if player := await resolve_player(interaction):
        await player.set_volume(level)
        await interaction.response.send_message(f"Volume set to {level}%.")


@bot.tree.command(description="Set the loop mode.")
@app_commands.describe(mode="What to loop.")
@app_commands.choices(mode=[
    app_commands.Choice(name="Off", value="off"),
    app_commands.Choice(name="Track", value="track"),
    app_commands.Choice(name="Queue", value="queue"),
])
async def loop(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
    if player := await resolve_player(interaction):
        player.queue.mode = {
            "off": wavelink.QueueMode.normal,
            "track": wavelink.QueueMode.loop,
            "queue": wavelink.QueueMode.loop_all,
        }[mode.value]
        await interaction.response.send_message(f"Loop set to **{mode.name}**.")


# --------------------------------------------------------------------------- #
# Queue commands
# --------------------------------------------------------------------------- #
@bot.tree.command(description="Show the upcoming tracks.")
async def queue(interaction: discord.Interaction) -> None:
    player = await resolve_player(interaction)
    if not player:
        return
    if player.queue.is_empty:
        await interaction.response.send_message("The queue is empty.", ephemeral=True)
        return

    upcoming = list(player.queue)[:10]
    lines = [f"`{index}.` {track.title}" for index, track in enumerate(upcoming, start=1)]
    if len(player.queue) > 10:
        lines.append(f"…and {len(player.queue) - 10} more")

    embed = discord.Embed(title="Queue", description="\n".join(lines), colour=discord.Colour.blurple())
    await interaction.response.send_message(embed=embed)


@bot.tree.command(description="Remove a track from the queue by its position.")
@app_commands.describe(position="The position shown in /queue.")
async def remove(interaction: discord.Interaction, position: int) -> None:
    player = await resolve_player(interaction)
    if not player:
        return
    index = position - 1
    if not 0 <= index < len(player.queue):
        await interaction.response.send_message("That position isn't in the queue.", ephemeral=True)
        return
    track = player.queue[index]
    del player.queue[index]
    await interaction.response.send_message(f"Removed **{track.title}**.")


@bot.tree.command(description="Clear the entire queue.")
async def clear(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction):
        player.queue.clear()
        await interaction.response.send_message("Queue cleared.")


@bot.tree.command(description="Shuffle the queue.")
async def shuffle(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction):
        player.queue.shuffle()
        await interaction.response.send_message("Queue shuffled.")


@bot.tree.command(description="Show the current track with playback controls.")
async def nowplaying(interaction: discord.Interaction) -> None:
    if player := await resolve_player(interaction, require_track=True):
        await interaction.response.send_message(
            embed=now_playing_embed(player.current), view=PlayerControls(player)
        )


@bot.tree.command(name="help", description="List every HydraX command.")
async def help_command(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="HydraX",
        description="A lightweight Discord music bot.",
        colour=discord.Colour.purple(),
    )
    embed.add_field(
        name="Playback",
        value="`/play` `/pause` `/resume` `/skip` `/stop` `/volume` `/loop` `/nowplaying`",
        inline=False,
    )
    embed.add_field(name="Queue", value="`/queue` `/remove` `/clear` `/shuffle`", inline=False)
    embed.set_footer(text="Developed by Rajnikant")
    await interaction.response.send_message(embed=embed)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    if not Settings.token:
        raise SystemExit("DISCORD_TOKEN is not set. Add it to your .env or host variables.")
    bot.run(Settings.token)


if __name__ == "__main__":
    main()
