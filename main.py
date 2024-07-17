import asyncio
import contextlib
import os
import re

import discord
import yt_dlp
from dotenv import load_dotenv
from Nueue.queue import Queue

load_dotenv()

ydl_options = {
    "format": "bestaudio",
    "noplaylist": "True",
    "quiet": "True",
    "skipdownload": "True",
    "extractflat": "True",
    "nocheckcertificate": "True",
}
ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -threads 4",
    "options": "-vn",
}


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(
        self,
        source: discord.AudioSource,
        *,
        data,
        volume: float = 0.5,
    ) -> None:
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.url = data.get("url")
        self.thumbnail = data.get("thumbnail")
        self.uploader = data.get("uploader")
        self.duration = data.get("duration")
        self.view_count = data.get("view_count")

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        ydl = yt_dlp.YoutubeDL(ydl_options)

        try:
            data = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(url, download=False),
            )
        except yt_dlp.utils.DownloadError as e:
            if "DRM" in str(e):
                return None, "DRM"
            data = await loop.run_in_executor(
                None,
                lambda: ydl.extract_info(f"ytsearch:{url}", download=False),
            )
            if not data["entries"]:
                return None, "No results"
            data = data["entries"][0]
        except Exception:
            return None, "Error"

        filename = data["url"]
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data), None


class Confirm(discord.ui.View):
    def __init__(self, ctx) -> None:
        super().__init__()
        self.is_playing = True
        self.ctx = ctx

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.grey)
    async def previous_callback(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        if not queue.source(True):
            embed = create_embed(self.ctx, "佇列中沒有上一首歌曲。", "error")
            await interaction.response.send_message(embed=embed)
            return
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.stop()
        await play_previous_song(self.ctx)
        embed = create_embed(self.ctx, queue.current_item(), "queue")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.grey)
    async def switch_callback(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.ctx.voice_client.resume()
            button.emoji = "⏸️"
            button.style = discord.ButtonStyle.grey
        else:
            self.ctx.voice_client.pause()
            button.emoji = "▶️"
            button.style = discord.ButtonStyle.green
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.grey)
    async def next_callback(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        if not queue.source():
            embed = create_embed(self.ctx, "佇列中沒有下一首歌曲。", "error")
            await interaction.response.send_message(embed=embed)
            return
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.stop()
        await play_next_song(self.ctx)
        embed = create_embed(self.ctx, queue.current_item(), "queue")
        await interaction.response.edit_message(embed=embed, view=self)


def create_embed(ctx: discord.ApplicationContext, player, mode: str) -> discord.Embed:
    if mode == "error":
        embed = discord.Embed(
            title="❌ 錯誤",
            description=player,
            color=discord.Color.red(),
        )
    if mode == "controller":
        embed = discord.Embed(
            title=player.title,
            url=player.url,
            description="",
            color=discord.Color.blue(),
        )
        embed.add_field(name="頻道名稱", value=player.uploader, inline=True)
        embed.add_field(
            name="影片時長",
            value=(
                (f"{player.duration // 60}:{player.duration % 60:02d}")
                if player.duration
                else "🔴 直播"
            ),
            inline=True,
        )
        embed.add_field(name="觀看次數", value=f"{player.view_count:,}", inline=True)
        embed.set_thumbnail(url=player.thumbnail)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url,  # type: ignore
        )
    elif mode == "queue":
        embed = discord.Embed(
            title=player.title,
            url=player.url,
            description="已在佇列中新增該歌曲。",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=player.thumbnail)
    embed.set_footer(
        text=f"Requested by {ctx.author.display_name}",
        icon_url=ctx.author.avatar.url,  # type: ignore
    )
    return embed


async def play_next_song(ctx: discord.ApplicationContext) -> None:
    global trigger
    player = queue.current_item() if trigger else queue.next()
    if player:
        new_player, error = await YTDLSource.from_url(player.url, loop=bot.loop)
        if error:
            embed = create_embed(ctx, f"發生未預期的錯誤\n```{error}```", "error")
            await ctx.respond(embed=embed)
            return

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        with contextlib.suppress(discord.errors.ClientException):
            ctx.voice_client.play(
                new_player,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next_song(ctx),
                    bot.loop,
                ).result(),
            )

        trigger = False
    else:
        embed = create_embed(ctx, "佇列中沒有下一首歌曲。", "error")
        await ctx.send_followup(embed=embed)


async def play_previous_song(ctx: discord.ApplicationContext) -> None:
    player = queue.previous()
    if player:
        new_player, error = await YTDLSource.from_url(player.url, loop=bot.loop)
        if error:
            embed = create_embed(ctx, f"發生未預期的錯誤\n```{error}```", "error")
            await ctx.respond(embed=embed)
            return

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

        with contextlib.suppress(discord.errors.ClientException):
            ctx.voice_client.play(
                new_player,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next_song(ctx),
                    bot.loop,
                ).result(),
            )
    else:
        embed = create_embed(ctx, "佇列中沒有上一首歌曲。", "error")
        await ctx.send_followup(embed=embed)


intents: discord.Intents = discord.Intents.all()
bot: discord.Bot = discord.Bot(intents=intents)
queue = Queue()
trigger: bool = True


@bot.event
async def on_ready() -> None:
    print(bot.user)


@bot.slash_command(description="提前讓我下班")
async def leave(ctx: discord.ApplicationContext) -> None:
    global trigger
    if ctx.voice_client:
        embed = discord.Embed(
            title="👋 掰掰",
            description="我先跑路了，明天也不會上班",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url,  # type: ignore,
        )
        await ctx.respond(embed=embed)
        await ctx.voice_client.disconnect(force=True)
        queue.clear()
        trigger = True
    else:
        embed = create_embed(ctx, "我還不在一個語音頻道。", "error")
        await ctx.respond(embed=embed)


@bot.slash_command(description="看看我的延遲")
async def ping(ctx: discord.ApplicationContext) -> None:
    await ctx.respond(f"Pong! ({bot.latency*1000:.2f} ms)")


@bot.slash_command(description="心情不好聽聽歌")
async def play(
    ctx: discord.ApplicationContext,
    query: str,
    controller: bool = False,
) -> None:
    global trigger
    await ctx.defer()
    if not ctx.author.voice:
        embed = create_embed(ctx, "請先加入一個語音頻道。", "error")
        await ctx.respond(embed=embed)
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    player, error = await YTDLSource.from_url(query, loop=bot.loop)
    if error:
        if error == "DRM":
            domain = re.findall(r"https?://(?:www\.)?([^/]+\.com)", query)[0]

            embed = create_embed(
                ctx,
                f"該網站 [{domain}]({query}) 含有DRM保護。",
                "error",
            )
            await ctx.respond(embed=embed)
            return
        elif error == "No results":
            embed = create_embed(
                ctx,
                f"找不到結果\n```{query}```",
                "error",
            )
            await ctx.respond(embed=embed)
            return
        else:
            embed = create_embed(
                ctx,
                f"發生未預期的錯誤\n```{error}```",
                "error",
            )
            await ctx.respond(embed=embed)
            return

    queue.add(player)

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

    if not error:
        if trigger or controller:
            await ctx.respond(
                embed=create_embed(ctx, player, "controller"),
                view=Confirm(ctx),
            )
            trigger = False
            return
        else:
            await ctx.respond(embed=create_embed(ctx, player, "queue"))
            trigger = False
            return


bot.run(os.getenv("TOKEN"))
