import discord
import json
from discord.ext import commands
from core.classes import Cog_Extension
from cmds.main import Main


with open('setting.json', 'r', encoding='utf8') as jFile:
    jdata = json.load(jFile)

class Event(Cog_Extension):
    @commands.Cog.listener()
    async def on_member_join(self, member):#成員加入事件
        channel = self.bot.get_channel(jdata['Welcome_channel'])
        await channel.send(f'{member} join!')
        print(f'```{member} join!```')

    @commands.Cog.listener()
    async def on_member_remove(self, member):#成員離開事件
        channel = self.bot.get_channel(jdata['Leave_channel'])
        await channel.send(f'{member} leave!')
        print(f'```{member} leave!```')

    @commands.Cog.listener()
    async def on_message(self, msg):
        #keyword = ['apple', 'pen', 'pie', 'abc']
        #if msg.content == 'apple' and msg.author != self.bot.user:
        #if msg.content.endswith('apple') and msg.author != self.bot.user:
        if msg.content in jdata['keyword'] and msg.author != self.bot.user:
            await msg.channel.send('apple')

    #處理"指令"發生的錯誤 Error Handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        #檢查指令是否有自己的error handler：如果有就跳過
        #if hasattr(ctx.command, 'on_error'):
        #    return

        if isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send(f'```遺失參數```')
        elif isinstance(error, commands.errors.CommandNotFound):
            await ctx.send(f'```找不到該指令```')
        else:
            await ctx.send(error)

    #指令個別專用的錯誤處理
    @Main.cmdB.error
    async def cmdB_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'```請輸入參數```')
    

def setup(bot):
    bot.add_cog(Event(bot))
