import asyncio
import youtube_dl
import discord

from discord.ext import commands
from core.classes import Cog_Extension
from collections import deque

play_list = {}
now_playing = {}
skip = {}

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

        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')

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

        self.title = data.get('title')
        self.url = data.get('url')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def get(self, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        return self(data=data)
    

def play_next(self, ctx):
    guild_id = ctx.message.guild.id
    if not skip[guild_id]:
        print('play next')
        guild_id = ctx.message.guild.id
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
        now_playing[guild_id] = None
        play_list[guild_id].popleft()
        mp = asyncio.run_coroutine_threadsafe(music_play(self, ctx), self.bot.loop)
        try:
            mp.result
        except:
            pass

async def music_play(self, ctx):
    print('Enter music player')
    
    guild_id = ctx.message.guild.id
    if guild_id not in play_list:
        play_list[guild_id] = (deque([]))
    
    if len(play_list[guild_id]):
        player = play_list[guild_id][0]

        now_playing[guild_id] = player
        player = await YTDLSource.from_YTDLInfo(player) 

        await ctx.send(f'Now playing: {player.title}\n{player.webpage_url}')
        print(f'Now playing: {player.title}\n{player.webpage_url}')
        #await asyncio.sleep(.2)
        ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else player.cleanup() or play_next(self, ctx))
    
    if guild_id not in skip:
        skip[guild_id] = False

async def add_play_list(ctx, player):
    guild_id = ctx.message.guild.id
    try:
        play_list[guild_id].append(player)
        return await asyncio.sleep(.1)
    except: 
        await ctx.send("can't add in to play_list")
        return await ctx.message.add_reaction('❌')

class Music(Cog_Extension):
    @commands.command(aliases=['p'])
    async def play(self, ctx, *, url):
        """Play music"""
        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.message.add_reaction('❌')
            return await ctx.send("I am not in a voice channel.")

        author_voice = ctx.message.author.voice
        if author_voice is None:
            return

        if voice_client.source and not now_playing:
            voice_client.stop()

        guild_id = ctx.message.guild.id
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
        
        #await ctx.message.delete()
        
        try:
            player = await YTDLInfo.get(url=url, loop=self.bot.loop)
            await add_play_list(ctx, player)

            if len(play_list[guild_id]) > 1:
                await ctx.send('Add in queue: {}\n{}'.format(player.title, player.webpage_url))    
            else:
                await music_play(self, ctx)
            await ctx.message.add_reaction('✅')
        except:
            await ctx.send('```Error. Please try again later.```')
            await ctx.message.add_reaction('❌')
        

    @commands.command(aliases=['lv'])
    async def leave(self, ctx):
        """Stops and disconnects the bot from voice"""
        guild_id = ctx.message.guild.id
        if guild_id in play_list:
            play_list[guild_id].clear()

        now_playing[guild_id] = None

        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.message.add_reaction('❌')
            return await ctx.send("I am not in a voice channel.")
        else:
            channel = voice_client.channel
            user = ctx.message.author.mention
            await voice_client.disconnect()
            if voice_client.is_playing():
                voice_client.stop()
            await ctx.send(f'{user}, Disconnected from {channel}')
            await ctx.message.add_reaction('✅')    

    @commands.command(aliases=['st'])
    async def stop(self, ctx):
        """Stops playing and clear the playlist"""
        guild_id = ctx.message.guild.id

        if guild_id in play_list:
            play_list[guild_id].clear()
        
        now_playing[guild_id] = None

        voice_client = ctx.voice_client
        if voice_client is None:
            await ctx.message.add_reaction('❌')
            return await ctx.send("I am not in a voice channel.")
        elif ctx.voice_client.is_playing():
            voice_client.stop()
        await ctx.message.add_reaction('✅')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            await ctx.message.add_reaction('❌')
            return await ctx.send("Not connected to a voice channel.")

        volume = min(100, max(0, volume))
        ctx.voice_client.source.volume = volume / 100
        await ctx.send("Changed volume to {}%".format(int(volume)))
        await ctx.message.add_reaction('✅')

    @commands.command(aliases=['j'])
    @play.before_invoke
    async def join(self, ctx):
        """Joins a voice channel"""
        voice = ctx.message.author.voice

        if voice is not None:
            channel = voice.channel
        else:
            await ctx.message.add_reaction('❌')
            return await ctx.send(f'{ctx.author.name} is not in a channel.')
        await ctx.message.add_reaction('☑')
        if ctx.voice_client is not None:
            '''
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            '''
            return await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

    @commands.command()
    async def pause(self, ctx):
        voice_client = ctx.voice_client
        
        if not voice_client:
            await ctx.message.add_reaction('❌')
            return await ctx.send("I am not in a voice channel.")

        if voice_client.is_playing():
            await ctx.message.add_reaction('✅')
            await ctx.send("Pause.")
            voice_client.pause()
        else:
            await ctx.message.add_reaction('❌')
            await ctx.send("Currently no audio is playing.")


    @commands.command()
    async def resume(self, ctx):
        voice_client = ctx.voice_client

        if not voice_client:
            await ctx.message.add_reaction('❌')
            await ctx.send("I am not in a voice channel.")
            return

        if voice_client.is_paused():
            await ctx.message.add_reaction('✅')
            await ctx.send("Resume.")
            voice_client.resume()
        else:
            await ctx.message.add_reaction('❌')
            await ctx.send("The audio is not paused.")

    @commands.command(aliases=['np'])
    async def nowplaying(self, ctx):
        voice_client = ctx.voice_client
        guild_id = ctx.message.guild.id

        if not voice_client:
            await ctx.message.add_reaction('❌')
            await ctx.send("I am not in a voice channel.")
            return
        if guild_id in now_playing:
            if now_playing[guild_id] is not None:
                await ctx.message.add_reaction('✅')
                return await ctx.send(f'Now playing: {now_playing[guild_id].title}\n{now_playing[guild_id].webpage_url}')

        await ctx.message.add_reaction('❌')
        await ctx.send('Nothing Playing Now!!')

    @commands.command(aliases=['sk'])
    async def skip(self, ctx, times=1):
        voice_client = ctx.voice_client
        guild_id = ctx.message.guild.id
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))

        if not voice_client:
            await ctx.message.add_reaction('❌')
            return await ctx.send("I am not in a voice channel.")
        else:
            if now_playing[guild_id] is None:
                await ctx.message.add_reaction('❌')
                return await ctx.send('Nothing Playing Now!!')
            else:
                skip[guild_id] = True
                await asyncio.sleep(.3)
                voice_client.stop()
                await ctx.message.add_reaction('✅')
                #skip_songs = f'Skip: {play_list[guild_id][0]}\n'
                skip_songs = ''
                #await ctx.send(f'Skip: {now_playing[guild_id].title}')
                
                play_list_length = len(play_list[guild_id])
                times = min(play_list_length, times)
                
                for i in range(times):
                    skip_songs += f'Skip: {play_list[guild_id][0].title}\n'
                    play_list[guild_id].popleft()

                await ctx.send(skip_songs)
                await music_play(self, ctx)
        skip[guild_id] = False
            
    @commands.command()
    async def source(self, ctx):
        voice_client = ctx.voice_client
        await ctx.send(voice_client.source)

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        cnt=1
        guild_id = ctx.message.guild.id
        queue_out = ''
        if guild_id not in play_list:
            play_list[guild_id] = (deque([]))
        for elem in play_list[guild_id]:
            queue_out += f'{cnt}.{elem.title}\n'
            cnt+=1
        if cnt != 1:
            await ctx.send(queue_out)
            await ctx.message.add_reaction('✅')
        else:
            await ctx.message.add_reaction('❌')

def setup(bot):
    bot.add_cog(Music(bot))