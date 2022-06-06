import asyncio
import youtube_dl
import discord
import time

from discord.ext import commands
from core.classes import Cog_Extension
from collections import deque
from urllib.parse import urlparse
from itertools import product


play_list = {}
now_playing = {}
skip = {}
loop_flag = {}

hhmmss = [f"{h:02d}:{m:02d}:{s:02d}"
             for h, m, s in product(range(24), range(60), range(60))]

mmss = [f"{m:02d}:{s:02d}"
             for m, s in product(range(60), range(60))]

seconds_to_str_hhmmss = hhmmss.__getitem__
seconds_to_str_mmss = mmss.__getitem__


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

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
    'no-cache-dir': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

'''
    streaming audio causes a known issue 
    https://stackoverflow.com/questions/63647546/how-would-i-stream-audio-from-pytube-to-ffmpeg-and-discord-py-without-downloadin
    https://support.discord.com/hc/fr/articles/360035010351--Known-Issue-Music-Bots-Not-Playing-Music-From-Certain-Sources
'''
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',

    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.url = data.get('url')

    @classmethod
    async def from_url(self, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return self(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
    
    @classmethod
    async def from_YTDLInfo(self, YTDLInfo):
        data = YTDLInfo.data
        filename = data['url']
        return self(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class YTDLInfo():
    def __init__(self, *, data):
        super().__init__()

        self.data = data
        self.start = None
        self.preplaytime = 0

        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')
        self.extractor_key = data.get('extractor_key')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        self.duration = data.get('duration')

    @classmethod
    async def get(self, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        return self(data=data)
    

def play_next(self, ctx, guild_id):
    if not skip[guild_id]:
        print('play next')
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
        if not loop_flag[guild_id]:     
            now_playing[guild_id] = None
            try:
                play_list[guild_id].popleft()
            except:
                pass
        mp = asyncio.run_coroutine_threadsafe(music_play(self, ctx), self.bot.loop)
        try:
            mp.result
        except:
            pass

async def music_play(self, ctx):
    print('Enter music player')
    
    guild_id = ctx.guild.id
    if guild_id not in play_list:
        play_list[guild_id] = (deque([]))
    
    if len(play_list[guild_id]):
        player = play_list[guild_id][0]

        now_playing[guild_id] = player
        player = await YTDLSource.from_YTDLInfo(player) 
        if not loop_flag[guild_id]:
            embed=discord.Embed(title=now_playing[guild_id].title, url=now_playing[guild_id].webpage_url, description=now_playing[guild_id].description, color=0x297524)
            embed.set_author(name="Now Playing")
            embed.set_thumbnail(url=now_playing[guild_id].thumbnail)
            embed.set_footer(text=f'{now_playing[guild_id].extractor_key}: {now_playing[guild_id].uploader}')
            await ctx.send(embed=embed)
        print(f'Now playing: {now_playing[guild_id].title}\n{now_playing[guild_id].webpage_url}')
        #await asyncio.sleep(.2)
        ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else player.cleanup() or play_next(self, ctx, guild_id))
        now_playing[guild_id].start = time.time()
    
    if guild_id not in skip:
        skip[guild_id] = False

class Music(Cog_Extension):
    @commands.slash_command()
    async def play(self, ctx, *, song):
        """Play music"""
        
        voice = ctx.author.voice
        voice_client = ctx.author.guild.voice_client
        if voice is not None:
            channel = voice.channel
        else:
            return await ctx.respond(f'{ctx.author.name} is not in a channel.')
        if voice_client is None:
            await channel.connect()
        else:
            await voice_client.move_to(channel)
            
        """Join part finished"""
        voice_client = ctx.author.guild.voice_client
        if voice_client.source and not now_playing:
            voice_client.stop()
        guild_id = ctx.author.guild.id
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
                
        await ctx.respond("Received Your Request.")
        #try:
        player = await YTDLInfo.get(url=song, loop=self.bot.loop)
        try:
            play_list[guild_id].append(player)
        except: 
            embed=discord.Embed(title="Can't add in to play_list", color=0x920202)
            await ctx.send(embed=embed)
  
        if len(play_list[guild_id]) > 1:
            embed=discord.Embed(title=player.title, url=player.webpage_url, description=player.description, color=0x297524)
            embed.set_author(name="Add to Queue")
            embed.set_thumbnail(url=player.thumbnail)
            embed.set_footer(text=f'{player.extractor_key}: {player.uploader}')
            await ctx.send(embed=embed)
            print(f'Add to queue: {player.title}\n{player.webpage_url}')
        else:
            try:
                loop_flag[guild_id] = False
                await music_play(self, ctx)
            except:
                embed=discord.Embed(title="Error. Please try again later", color=0x920202)
                await ctx.send(embed=embed)
        
    @commands.slash_command()
    async def leave(self, ctx):
        """Stops and disconnects the bot from voice"""
        guild_id = ctx.guild.id
        if guild_id in play_list:
            play_list[guild_id].clear()

        now_playing[guild_id] = None

        voice_client = ctx.voice_client
        if voice_client is None:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)
        else:
            channel = voice_client.channel
            await voice_client.disconnect()
            if voice_client.is_playing():
                voice_client.stop()
            embed=discord.Embed(title=f'Disconnected from {channel}', color=0x297524)
            await ctx.respond(embed=embed)

    @commands.slash_command()
    async def stop(self, ctx):
        """Stops playing and clear the playlist"""
        guild_id = ctx.guild.id

        if guild_id in play_list:
            play_list[guild_id].clear()
        
        now_playing[guild_id] = None

        voice_client = ctx.voice_client
        if voice_client is None:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)
        elif ctx.voice_client.is_playing():
            voice_client.stop()
        embed=discord.Embed(title=f'Success!', color=0x297524)
        return await ctx.respond(embed=embed)

    @commands.slash_command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)

        volume = min(100, max(0, volume))
        ctx.voice_client.source.volume = volume / 100
        embed=discord.Embed(title=f'Changed volume to {int(volume)}%', color=0x297524)
        return await ctx.respond(embed=embed)

    @commands.slash_command()
    async def join(self, ctx):
        """Joins a voice channel"""
        voice = ctx.author.voice
        voice_client = ctx.author.guild.voice_client
        if voice is not None:
            channel = voice.channel
        else:
            embed=discord.Embed(title=f'{ctx.author.name} is not in a channel.', color=0x920202)
            return await ctx.respond(embed=embed)
        if voice_client is None:
            await channel.connect()
        else:
            await voice_client.move_to(channel)
        embed=discord.Embed(title=f'Success!', color=0x297524)
        return await ctx.respond(embed=embed)

    @commands.slash_command()
    async def pause(self, ctx):
        """Pause current song"""
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        
        if not voice_client:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)

        if voice_client.is_playing():
            embed=discord.Embed(title=f'Pause', color=0x297524)
            await ctx.respond(embed=embed)
            now_playing[guild_id].preplaytime = time.time() - now_playing[guild_id].start + now_playing[guild_id].preplaytime
            return voice_client.pause()
        else:
            embed=discord.Embed(title=f'Currently no audio is playing', color=0x297524)
            return await ctx.respond(embed=embed)

    @commands.slash_command()
    async def resume(self, ctx):
        """Resume paused song"""
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id

        if not voice_client:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)

        if voice_client.is_paused():
            embed=discord.Embed(title=f'Resume', color=0x297524)
            await ctx.respond(embed=embed)
            now_playing[guild_id].start = time.time()
            return voice_client.resume()
        else:
            embed=discord.Embed(title=f'No audio was paused', color=0x297524)
            return await ctx.respond(embed=embed)
    
    @commands.slash_command()
    async def loop(self, ctx):
        """loop current song"""
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        
        if not voice_client:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)

        if voice_client.is_playing():
            global loop_flag
            if loop_flag[guild_id]:
                loop_flag[guild_id] = False
                embed=discord.Embed(title=f'Stop Loop', color=0x297524)
            else:
                loop_flag[guild_id] = True
                embed=discord.Embed(title=f'Loop Current Song', color=0x297524)
            return await ctx.respond(embed=embed)
        else:
            embed=discord.Embed(title=f'Currently no audio is playing', color=0x297524)
            return await ctx.respond(embed=embed)

    @commands.slash_command()
    async def nowplaying(self, ctx):
        """Show playing song"""
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id

        if not voice_client:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)
        if guild_id in now_playing:
            if now_playing[guild_id] is not None:
                if voice_client.is_paused():
                    current = now_playing[guild_id].preplaytime
                else:
                    current = time.time() - now_playing[guild_id].start + now_playing[guild_id].preplaytime
                end = now_playing[guild_id].duration
                if current >= 3600:
                    current_str = seconds_to_str_hhmmss(int(current))
                else:
                    current_str = seconds_to_str_mmss(int(current))
                if end >= 3600:
                    end_str = seconds_to_str_hhmmss(int(end))
                else:
                    end_str = seconds_to_str_mmss(int(end))
                bar = '▓' * int((current/end)*30)
                embed=discord.Embed(title=now_playing[guild_id].title, url=now_playing[guild_id].webpage_url, description=now_playing[guild_id].description, color=0x297524)
                embed.set_author(name="Now Playing")
                embed.set_thumbnail(url=now_playing[guild_id].thumbnail)
                #print(bar)
                embed.add_field(name=f'{current_str:⠀<17}{end_str:⠀>17}', value=f'[{bar:⠀<30}]', inline=True)
                embed.set_footer(text=f'{now_playing[guild_id].extractor_key}: {now_playing[guild_id].uploader}')
                return await ctx.respond(embed=embed)

        embed=discord.Embed(title=f'Nothing Playing Now!!', color=0x297524)
        

    @commands.slash_command()
    async def skip(self, ctx, times=1):
        """Skip current song"""
        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))

        if not voice_client:
            embed=discord.Embed(title="No Voice Channel", color=0x920202)
            return await ctx.respond(embed=embed)
        else:
            if now_playing[guild_id] is None:
                embed=discord.Embed(title=f'Nothing Playing Now!!', color=0x297524)
                return await ctx.respond(embed=embed)
            else:
                skip[guild_id] = True
                await asyncio.sleep(.3)
                voice_client.stop()
                skip_songs = ''
                
                play_list_length = len(play_list[guild_id])
                times = min(play_list_length, times)
                
                for i in range(times):
                    skip_songs += f'Skip: {play_list[guild_id][0].title}\n'
                    play_list[guild_id].popleft()

                await ctx.respond(skip_songs)
                await music_play(self, ctx)
        skip[guild_id] = False
            
    @commands.slash_command()
    async def source(self, ctx):
        """Show audio source(debug only)"""
        voice_client = ctx.voice_client
        await ctx.respond(voice_client.source)

    @commands.slash_command()
    async def queue(self, ctx):
        """List songs"""
        cnt=1
        guild_id = ctx.guild.id
        queue_out = ''
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
        for elem in play_list[guild_id]:
            queue_out += f'{cnt}.{elem.title}\n'
            cnt+=1
        if cnt != 1:
            await ctx.respond(queue_out)
        else:
            await ctx.respond("Empty!!")

def setup(bot):
    bot.add_cog(Music(bot))
