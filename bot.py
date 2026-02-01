import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import os
from dotenv import load_dotenv
import yt_dlp
from aiohttp import web
import json
import threading

# โหลด environment variables
load_dotenv()

# ตั้งค่า intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# สร้าง bot
bot = commands.Bot(command_prefix="!", intents=intents)

# ตั้งค่า yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extract_flat': False,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# เก็บข้อมูลสำหรับแต่ละ server
class GuildMusicData:
    def __init__(self):
        self.queue = []  # [(url, title)]
        self.current_song = None
        self.is_playing = False
        self.volume = 0.5
        self.loop = False
        self.message = None  # เก็บ message สำหรับ update ปุ่ม
        self.is_247 = False  # โหมด 24/7
        self.voice_channel_id = None  # ห้องเสียงสำหรับ 24/7

guild_data = {}

def get_guild_data(guild_id):
    if guild_id not in guild_data:
        guild_data[guild_id] = GuildMusicData()
    return guild_data[guild_id]

# ปุ่มควบคุมเพลง
class MusicControlView(ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
    
    @ui.button(label="⏸️ หยุด", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            button.label = "▶️ เล่นต่อ"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        elif interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            button.label = "⏸️ หยุด"
            button.style = discord.ButtonStyle.secondary
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("❌ ไม่มีเพลงกำลังเล่น", ephemeral=True)
    
    @ui.button(label="⏭️ ข้าม", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏭️ ข้ามเพลงแล้ว!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่มีเพลงกำลังเล่น", ephemeral=True)
    
    @ui.button(label="⏹️ หยุดเล่น", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        data = get_guild_data(interaction.guild.id)
        data.queue.clear()
        data.current_song = None
        
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("⏹️ หยุดเล่นและล้างคิวแล้ว!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่มีเพลงกำลังเล่น", ephemeral=True)
    
    @ui.button(label="📜 ดูคิว", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        data = get_guild_data(interaction.guild.id)
        
        embed = discord.Embed(
            title="📜 คิวเพลง",
            color=discord.Color.blue()
        )
        
        # เพลงปัจจุบัน
        if data.current_song:
            embed.add_field(
                name="🎵 กำลังเล่น",
                value=f"**{data.current_song}**",
                inline=False
            )
        
        # คิวเพลง
        if len(data.queue) > 0:
            queue_text = ""
            for i, (url, title) in enumerate(data.queue[:10], 1):
                queue_text += f"`{i}.` {title}\n"
            
            if len(data.queue) > 10:
                queue_text += f"\n*และอีก {len(data.queue) - 10} เพลง...*"
            
            embed.add_field(name="📝 รออยู่ในคิว", value=queue_text, inline=False)
        else:
            embed.add_field(name="📝 คิว", value="*ว่างเปล่า*", inline=False)
        
        embed.set_footer(text=f"รวม {len(data.queue)} เพลงในคิว")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @ui.button(label="🔊 เสียง +", style=discord.ButtonStyle.secondary)
    async def volume_up_button(self, interaction: discord.Interaction, button: ui.Button):
        data = get_guild_data(interaction.guild.id)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            data.volume = min(1.0, data.volume + 0.1)
            interaction.guild.voice_client.source.volume = data.volume
            await interaction.response.send_message(f"🔊 ระดับเสียง: {int(data.volume * 100)}%", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่มีเพลงกำลังเล่น", ephemeral=True)
    
    @ui.button(label="🔉 เสียง -", style=discord.ButtonStyle.secondary)
    async def volume_down_button(self, interaction: discord.Interaction, button: ui.Button):
        data = get_guild_data(interaction.guild.id)
        if interaction.guild.voice_client and interaction.guild.voice_client.source:
            data.volume = max(0.0, data.volume - 0.1)
            interaction.guild.voice_client.source.volume = data.volume
            await interaction.response.send_message(f"🔉 ระดับเสียง: {int(data.volume * 100)}%", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ไม่มีเพลงกำลังเล่น", ephemeral=True)
    
    @ui.button(label="🚪 ออก", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: ui.Button):
        data = get_guild_data(interaction.guild.id)
        data.queue.clear()
        data.current_song = None
        data.is_247 = False  # ปิดโหมด 24/7
        
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("👋 ออกจากห้องเสียงแล้ว!", ephemeral=True)
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("❌ บอทไม่ได้อยู่ในห้องเสียง", ephemeral=True)

async def play_next(ctx):
    data = get_guild_data(ctx.guild.id)
    
    if len(data.queue) > 0:
        url, title = data.queue.pop(0)
        await play_song(ctx, url, title)
    else:
        data.current_song = None
        data.is_playing = False

async def play_song(ctx, url, title=None):
    data = get_guild_data(ctx.guild.id)
    
    try:
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        data.current_song = player.title
        data.is_playing = True
        player.volume = data.volume
        
        def after_playing(error):
            if error:
                print(f'Player error: {error}')
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        ctx.voice_client.play(player, after=after_playing)
        
        # สร้าง embed แสดงเพลงที่กำลังเล่น พร้อมปุ่มควบคุม
        embed = discord.Embed(
            title="🎵 กำลังเล่น",
            description=f"**{player.title}**",
            color=discord.Color.green()
        )
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        if player.duration:
            minutes, seconds = divmod(player.duration, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                embed.add_field(name="⏱️ ระยะเวลา", value=f"{hours}:{minutes:02d}:{seconds:02d}")
            else:
                embed.add_field(name="⏱️ ระยะเวลา", value=f"{minutes}:{seconds:02d}")
        if player.webpage_url:
            embed.add_field(name="🔗 ลิงก์", value=f"[YouTube]({player.webpage_url})")
        
        # แสดงคิวถัดไป
        if len(data.queue) > 0:
            next_songs = "\n".join([f"`{i+1}.` {t}" for i, (u, t) in enumerate(data.queue[:3])])
            if len(data.queue) > 3:
                next_songs += f"\n*...และอีก {len(data.queue) - 3} เพลง*"
            embed.add_field(name="📜 ถัดไปในคิว", value=next_songs, inline=False)
        
        embed.set_footer(text=f"🔊 ระดับเสียง: {int(data.volume * 100)}%")
        
        view = MusicControlView(ctx)
        data.message = await ctx.send(embed=embed, view=view)
        
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        print(f"Error playing song: {e}")

async def get_song_info(query):
    """ดึงข้อมูลเพลงจาก URL หรือค้นหา"""
    try:
        if not query.startswith('http'):
            query = f"ytsearch:{query}"
        
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        return data.get('webpage_url', query), data.get('title', 'Unknown')
    except Exception as e:
        print(f"Error getting song info: {e}")
        return query, "Unknown"

# Event: ตรวจสอบเมื่อบอทถูก disconnect และ reconnect ถ้าเปิด 24/7
@bot.event
async def on_voice_state_update(member, before, after):
    # ตรวจสอบว่าเป็นบอทหรือไม่
    if member.id != bot.user.id:
        return
    
    # ถ้าบอทถูก disconnect
    if before.channel is not None and after.channel is None:
        data = get_guild_data(member.guild.id)
        
        # ถ้าเปิดโหมด 24/7 ให้ reconnect
        if data.is_247 and data.voice_channel_id:
            await asyncio.sleep(2)  # รอ 2 วินาที
            try:
                channel = bot.get_channel(data.voice_channel_id)
                if channel:
                    await channel.connect(timeout=60.0, reconnect=True)
                    print(f"🔄 Reconnected to {channel.name} (24/7 mode)")
            except Exception as e:
                print(f"❌ Failed to reconnect: {e}")

# คำสั่ง: เข้าห้องเสียง
@bot.command(name='join', aliases=['j', 'เข้า'])
async def join(ctx):
    """เข้าร่วมห้องเสียงของคุณ"""
    if ctx.author.voice is None:
        await ctx.send("❌ คุณต้องอยู่ในห้องเสียงก่อน!")
        return
    
    channel = ctx.author.voice.channel
    
    try:
        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect(timeout=60.0, reconnect=True)
        
        await ctx.send(f"✅ เข้าร่วม **{channel.name}** แล้ว!")
    except Exception as e:
        await ctx.send(f"❌ ไม่สามารถเข้าร่วมห้องเสียงได้: {str(e)}")

# คำสั่ง: เล่นเพลง
@bot.command(name='play', aliases=['p', 'เล่น'])
async def play(ctx, *, query: str):
    """เล่นเพลงจาก YouTube (URL หรือชื่อเพลง)"""
    data = get_guild_data(ctx.guild.id)
    
    # เข้าห้องเสียงถ้ายังไม่ได้เข้า
    if ctx.voice_client is None:
        if ctx.author.voice:
            try:
                await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)
            except Exception as e:
                await ctx.send(f"❌ ไม่สามารถเข้าร่วมห้องเสียงได้: {str(e)}")
                return
        else:
            await ctx.send("❌ คุณต้องอยู่ในห้องเสียงก่อน!")
            return
    
    async with ctx.typing():
        # ดึงข้อมูลเพลง
        url, title = await get_song_info(query)
        
        # ถ้ากำลังเล่นเพลงอยู่ ให้เพิ่มเข้า queue
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            data.queue.append((url, title))
            
            embed = discord.Embed(
                title="📝 เพิ่มเพลงเข้าคิว",
                description=f"**{title}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="ตำแหน่งในคิว", value=f"#{len(data.queue)}")
            await ctx.send(embed=embed)
        else:
            await play_song(ctx, url, title)

# คำสั่ง: หยุดชั่วคราว
@bot.command(name='pause', aliases=['หยุด'])
async def pause(ctx):
    """หยุดเพลงชั่วคราว"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ หยุดเพลงชั่วคราว")
    else:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่นอยู่")

# คำสั่ง: เล่นต่อ
@bot.command(name='resume', aliases=['r', 'ต่อ'])
async def resume(ctx):
    """เล่นเพลงต่อ"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ เล่นเพลงต่อ")
    else:
        await ctx.send("❌ ไม่มีเพลงที่หยุดอยู่")

# คำสั่ง: ข้ามเพลง
@bot.command(name='skip', aliases=['s', 'ข้าม'])
async def skip(ctx):
    """ข้ามเพลงปัจจุบัน"""
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        ctx.voice_client.stop()
        await ctx.send("⏭️ ข้ามเพลงแล้ว")
    else:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่นอยู่")

# คำสั่ง: หยุดเล่น
@bot.command(name='stop', aliases=['หยุดเล่น'])
async def stop(ctx):
    """หยุดเล่นและล้างคิว"""
    data = get_guild_data(ctx.guild.id)
    data.queue.clear()
    data.current_song = None
    
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏹️ หยุดเล่นและล้างคิวแล้ว")
    else:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่นอยู่")

# คำสั่ง: ออกจากห้องเสียง
@bot.command(name='leave', aliases=['l', 'dc', 'disconnect', 'ออก'])
async def leave(ctx):
    """ออกจากห้องเสียง"""
    data = get_guild_data(ctx.guild.id)
    
    if ctx.voice_client:
        data.queue.clear()
        data.current_song = None
        data.is_247 = False  # ปิดโหมด 24/7
        await ctx.voice_client.disconnect()
        await ctx.send("👋 ออกจากห้องเสียงแล้ว! (ปิดโหมด 24/7)")
    else:
        await ctx.send("❌ บอทไม่ได้อยู่ในห้องเสียง")

# คำสั่ง: โหมด 24/7
@bot.command(name='247', aliases=['24/7', 'stay', 'อยู่'])
async def mode_247(ctx):
    """เปิด/ปิดโหมด 24/7 - บอทจะอยู่ในห้องเสียงตลอด"""
    data = get_guild_data(ctx.guild.id)
    
    # ถ้ายังไม่ได้อยู่ในห้องเสียง ให้เข้าก่อน
    if ctx.voice_client is None:
        if ctx.author.voice:
            try:
                await ctx.author.voice.channel.connect(timeout=60.0, reconnect=True)
            except Exception as e:
                await ctx.send(f"❌ ไม่สามารถเข้าร่วมห้องเสียงได้: {str(e)}")
                return
        else:
            await ctx.send("❌ คุณต้องอยู่ในห้องเสียงก่อน!")
            return
    
    # Toggle โหมด 24/7
    data.is_247 = not data.is_247
    
    if data.is_247:
        data.voice_channel_id = ctx.voice_client.channel.id
        embed = discord.Embed(
            title="🌙 โหมด 24/7 เปิดแล้ว!",
            description=f"บอทจะอยู่ใน **{ctx.voice_client.channel.name}** ตลอด 24 ชั่วโมง",
            color=discord.Color.green()
        )
        embed.add_field(name="📌 หมายเหตุ", value="- บอทจะ reconnect อัตโนมัติถ้าถูก disconnect\n- ใช้ `!leave` เพื่อปิดโหมดและออกจากห้อง", inline=False)
        await ctx.send(embed=embed)
    else:
        data.voice_channel_id = None
        embed = discord.Embed(
            title="☀️ โหมด 24/7 ปิดแล้ว",
            description="บอทจะไม่ reconnect อัตโนมัติอีกต่อไป",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

# คำสั่ง: ดูคิว
@bot.command(name='queue', aliases=['q', 'คิว', 'list', 'ลิสต์'])
async def queue_cmd(ctx):
    """แสดงคิวเพลง"""
    data = get_guild_data(ctx.guild.id)
    
    embed = discord.Embed(
        title="📜 คิวเพลง",
        color=discord.Color.blue()
    )
    
    # เพลงปัจจุบัน
    if data.current_song:
        embed.add_field(
            name="🎵 กำลังเล่น",
            value=f"**{data.current_song}**",
            inline=False
        )
    
    # คิวเพลง
    if len(data.queue) > 0:
        queue_text = ""
        for i, (url, title) in enumerate(data.queue[:15], 1):
            queue_text += f"`{i}.` {title}\n"
        
        if len(data.queue) > 15:
            queue_text += f"\n*...และอีก {len(data.queue) - 15} เพลง*"
        
        embed.add_field(name="📝 รออยู่ในคิว", value=queue_text, inline=False)
    else:
        embed.add_field(name="📝 คิว", value="*ว่างเปล่า*", inline=False)
    
    embed.set_footer(text=f"รวม {len(data.queue)} เพลงในคิว | ใช้ !play เพื่อเพิ่มเพลง")
    await ctx.send(embed=embed)

# คำสั่ง: ล้างคิว
@bot.command(name='clear', aliases=['c', 'ล้าง'])
async def clear_queue(ctx):
    """ล้างคิวเพลงทั้งหมด"""
    data = get_guild_data(ctx.guild.id)
    count = len(data.queue)
    data.queue.clear()
    await ctx.send(f"🗑️ ล้างคิวแล้ว ({count} เพลง)")

# คำสั่ง: ลบเพลงจากคิว
@bot.command(name='remove', aliases=['rm', 'ลบ'])
async def remove_song(ctx, position: int):
    """ลบเพลงจากคิวตามตำแหน่ง"""
    data = get_guild_data(ctx.guild.id)
    
    if position < 1 or position > len(data.queue):
        await ctx.send(f"❌ ตำแหน่งไม่ถูกต้อง (1-{len(data.queue)})")
        return
    
    removed = data.queue.pop(position - 1)
    await ctx.send(f"🗑️ ลบ **{removed[1]}** ออกจากคิวแล้ว")

# คำสั่ง: ปรับเสียง
@bot.command(name='volume', aliases=['v', 'vol', 'เสียง'])
async def volume(ctx, vol: int):
    """ปรับระดับเสียง (0-100)"""
    data = get_guild_data(ctx.guild.id)
    
    if ctx.voice_client is None:
        await ctx.send("❌ บอทไม่ได้อยู่ในห้องเสียง")
        return
    
    if not 0 <= vol <= 100:
        await ctx.send("❌ ระดับเสียงต้องอยู่ระหว่าง 0-100")
        return
    
    data.volume = vol / 100
    if ctx.voice_client.source:
        ctx.voice_client.source.volume = data.volume
    
    await ctx.send(f"🔊 ปรับระดับเสียงเป็น {vol}%")

# คำสั่ง: ดูข้อมูลเพลงปัจจุบัน
@bot.command(name='nowplaying', aliases=['np', 'ตอนนี้'])
async def nowplaying(ctx):
    """แสดงเพลงที่กำลังเล่นอยู่"""
    data = get_guild_data(ctx.guild.id)
    
    if ctx.voice_client and ctx.voice_client.source and data.current_song:
        embed = discord.Embed(
            title="🎵 กำลังเล่น",
            description=f"**{data.current_song}**",
            color=discord.Color.purple()
        )
        embed.add_field(name="🔊 ระดับเสียง", value=f"{int(data.volume * 100)}%")
        embed.add_field(name="📜 เพลงในคิว", value=f"{len(data.queue)} เพลง")
        
        view = MusicControlView(ctx)
        await ctx.send(embed=embed, view=view)
    else:
        await ctx.send("❌ ไม่มีเพลงกำลังเล่นอยู่")

# คำสั่ง: ช่วยเหลือ
@bot.command(name='help_music', aliases=['h', 'ช่วยเหลือ'])
async def help_music(ctx):
    """แสดงคำสั่งทั้งหมด"""
    embed = discord.Embed(
        title="🎵 คำสั่ง Music Bot",
        description="รายการคำสั่งทั้งหมด",
        color=discord.Color.gold()
    )
    
    commands_list = [
        ("🎵 **เล่นเพลง**", "`!play <ชื่อ/URL>` - เล่นหรือเพิ่มเพลงเข้าคิว"),
        ("⏸️ **หยุด/เล่นต่อ**", "`!pause` / `!resume`"),
        ("⏭️ **ข้ามเพลง**", "`!skip` - ข้ามไปเพลงถัดไป"),
        ("⏹️ **หยุดเล่น**", "`!stop` - หยุดและล้างคิว"),
        ("📜 **ดูคิว**", "`!queue` หรือ `!list` - แสดงรายการเพลง"),
        ("🗑️ **จัดการคิว**", "`!clear` ล้างคิว / `!remove <เลข>` ลบเพลง"),
        ("🔊 **ปรับเสียง**", "`!volume <0-100>` - ปรับระดับเสียง"),
        ("🎵 **เพลงปัจจุบัน**", "`!np` - ดูเพลงที่กำลังเล่น"),
        ("🚪 **เข้า/ออก**", "`!join` เข้าห้อง / `!leave` ออกจากห้อง"),
        ("🌙 **24/7 Mode**", "`!247` - เปิด/ปิดโหมดอยู่ห้องตลอด 24 ชม."),
    ]
    
    for name, value in commands_list:
        embed.add_field(name=name, value=value, inline=False)
    
    embed.set_footer(text="💡 ใช้ปุ่มด้านล่างเพลงเพื่อควบคุมได้เลย!")
    await ctx.send(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ กรุณาใส่ข้อมูลให้ครบ! ใช้ `!help_music` เพื่อดูวิธีใช้")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(error)}")
        print(f'Error: {error}')

# รันบอท
if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if token is None:
        print("❌ ไม่พบ DISCORD_TOKEN ใน .env")
    else:
        print("🚀 กำลังเริ่มบอท...")
        bot.run(token)

# ================== API SERVER ==================

# API Port
API_PORT = int(os.getenv('API_PORT', 5000))
API_SECRET = os.getenv('API_SECRET', '')  # Optional secret key
DEFAULT_GUILD_ID = int(os.getenv('DEFAULT_GUILD_ID', 0))

# CORS Headers
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# API Routes
async def api_status(request):
    """Get bot status and current playing info"""
    try:
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            # ใช้ guild แรกที่พบ
            for g in bot.guilds:
                guild = g
                break
        
        if not guild:
            response = web.json_response({
                'online': True,
                'current_song': None,
                'queue': [],
                'is_247': False,
                'volume': 50
            })
            return add_cors_headers(response)
        
        data = get_guild_data(guild.id)
        voice_client = guild.voice_client
        
        # Get queue with titles
        queue_list = [{'title': title, 'url': url} for url, title in data.queue]
        
        response_data = {
            'online': True,
            'current_song': data.current_song,
            'thumbnail': getattr(voice_client.source, 'thumbnail', None) if voice_client and voice_client.source else None,
            'duration': None,
            'queue': queue_list,
            'is_247': data.is_247,
            'volume': int(data.volume * 100),
            'is_playing': voice_client.is_playing() if voice_client else False,
            'is_paused': voice_client.is_paused() if voice_client else False,
            'server_name': guild.name,
            'voice_channel': voice_client.channel.name if voice_client and voice_client.channel else None,
            'listeners': len(voice_client.channel.members) - 1 if voice_client and voice_client.channel else 0
        }
        
        response = web.json_response(response_data)
        return add_cors_headers(response)
    except Exception as e:
        print(f"API Error: {e}")
        response = web.json_response({'error': str(e)}, status=500)
        return add_cors_headers(response)

async def api_command(request):
    """Execute a command"""
    try:
        body = await request.json()
        command = body.get('command')
        
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if not guild:
            response = web.json_response({'success': False, 'message': 'ไม่พบเซิร์ฟเวอร์'})
            return add_cors_headers(response)
        
        voice_client = guild.voice_client
        data = get_guild_data(guild.id)
        
        message = ''
        
        if command == 'pause':
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                message = 'หยุดเพลงชั่วคราว'
            else:
                message = 'ไม่มีเพลงกำลังเล่น'
                
        elif command == 'resume':
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                message = 'เล่นเพลงต่อ'
            else:
                message = 'ไม่มีเพลงที่หยุดอยู่'
                
        elif command == 'skip':
            if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
                voice_client.stop()
                message = 'ข้ามเพลงแล้ว'
            else:
                message = 'ไม่มีเพลงกำลังเล่น'
                
        elif command == 'stop':
            data.queue.clear()
            data.current_song = None
            if voice_client:
                voice_client.stop()
            message = 'หยุดเล่นและล้างคิวแล้ว'
            
        elif command == 'leave':
            data.queue.clear()
            data.current_song = None
            data.is_247 = False
            if voice_client:
                await voice_client.disconnect()
            message = 'ออกจากห้องเสียงแล้ว'
        
        response = web.json_response({'success': True, 'message': message})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def api_play(request):
    """Add a song to queue"""
    try:
        body = await request.json()
        query = body.get('query')
        
        if not query:
            response = web.json_response({'success': False, 'message': 'กรุณาใส่ชื่อเพลง'})
            return add_cors_headers(response)
        
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if not guild:
            response = web.json_response({'success': False, 'message': 'ไม่พบเซิร์ฟเวอร์'})
            return add_cors_headers(response)
        
        data = get_guild_data(guild.id)
        
        # Get song info
        url, title = await get_song_info(query)
        
        voice_client = guild.voice_client
        
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            data.queue.append((url, title))
            message = f'เพิ่ม "{title}" เข้าคิว (#{len(data.queue)})'
        else:
            data.queue.append((url, title))
            message = f'เพิ่ม "{title}" แล้ว'
        
        response = web.json_response({'success': True, 'message': message, 'title': title})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def api_volume(request):
    """Set volume"""
    try:
        body = await request.json()
        volume = body.get('volume', 50)
        
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if guild:
            data = get_guild_data(guild.id)
            data.volume = volume / 100
            
            voice_client = guild.voice_client
            if voice_client and voice_client.source:
                voice_client.source.volume = data.volume
        
        response = web.json_response({'success': True, 'volume': volume})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def api_247(request):
    """Toggle 24/7 mode"""
    try:
        body = await request.json()
        enabled = body.get('enabled', False)
        
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if guild:
            data = get_guild_data(guild.id)
            data.is_247 = enabled
            
            if enabled and guild.voice_client:
                data.voice_channel_id = guild.voice_client.channel.id
            elif not enabled:
                data.voice_channel_id = None
        
        message = 'เปิดโหมด 24/7 แล้ว' if enabled else 'ปิดโหมด 24/7 แล้ว'
        response = web.json_response({'success': True, 'message': message, 'is_247': enabled})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def api_remove(request):
    """Remove song from queue"""
    try:
        body = await request.json()
        position = body.get('position', 1)
        
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if guild:
            data = get_guild_data(guild.id)
            if 1 <= position <= len(data.queue):
                removed = data.queue.pop(position - 1)
                message = f'ลบ "{removed[1]}" ออกจากคิวแล้ว'
            else:
                message = 'ตำแหน่งไม่ถูกต้อง'
        else:
            message = 'ไม่พบเซิร์ฟเวอร์'
        
        response = web.json_response({'success': True, 'message': message})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def api_clear(request):
    """Clear queue"""
    try:
        guild = None
        if DEFAULT_GUILD_ID:
            guild = bot.get_guild(DEFAULT_GUILD_ID)
        else:
            for g in bot.guilds:
                guild = g
                break
        
        if guild:
            data = get_guild_data(guild.id)
            count = len(data.queue)
            data.queue.clear()
            message = f'ล้างคิวแล้ว ({count} เพลง)'
        else:
            message = 'ไม่พบเซิร์ฟเวอร์'
        
        response = web.json_response({'success': True, 'message': message})
        return add_cors_headers(response)
    except Exception as e:
        response = web.json_response({'success': False, 'message': str(e)})
        return add_cors_headers(response)

async def handle_options(request):
    """Handle CORS preflight"""
    response = web.Response()
    return add_cors_headers(response)

# Create API app
def create_api_app():
    app = web.Application()
    app.router.add_get('/api/status', api_status)
    app.router.add_post('/api/command', api_command)
    app.router.add_post('/api/play', api_play)
    app.router.add_post('/api/volume', api_volume)
    app.router.add_post('/api/247', api_247)
    app.router.add_post('/api/remove', api_remove)
    app.router.add_post('/api/clear', api_clear)
    app.router.add_options('/{path:.*}', handle_options)
    return app

# Run API server
async def start_api_server():
    app = create_api_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', API_PORT)
    await site.start()
    print(f"🌐 API Server running on http://0.0.0.0:{API_PORT}")

# Start API when bot is ready
@bot.event
async def on_ready():
    print(f'✅ {bot.user} พร้อมใช้งานแล้ว!')
    print(f'📊 เชื่อมต่อกับ {len(bot.guilds)} เซิร์ฟเวอร์')
    
    # Start API server
    await start_api_server()
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'🔄 ซิงค์ {len(synced)} คำสั่งแล้ว')
    except Exception as e:
        print(f'❌ ซิงค์คำสั่งล้มเหลว: {e}')
    
    # ตั้งค่าสถานะ
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, 
        name="!play | !247"
    ))
