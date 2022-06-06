import discord, json, os
from dotenv import load_dotenv
from discord.ext import commands
load_dotenv()

TOKEN = os.getenv("TOKEN")

with open('setting.json', 'r', encoding='utf8') as jfile:
    jdata = json.load(jfile)

bot = commands.Bot(command_prefix=commands.when_mentioned_or(jdata['Prefix']))

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"Music | /play"))
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.slash_command()
async def hello(ctx):
    await ctx.respond("Hello!")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello!")

@bot.command()
async def load(ctx, extension):
    bot.load_extension(f'cmds.{extension}')
    await ctx.send(f'```Loaded {extension} done.```')
    
@bot.slash_command()
async def load(ctx, extension):
    bot.load_extension(f'cmds.{extension}')
    await ctx.respond(f'```Loaded {extension} done.```')

#@bot.command()
@bot.slash_command()
async def unload(ctx, extension):
    bot.unload_extension(f'cmds.{extension}')
    await ctx.respond(f'```Un - Loaded {extension} done.```')

#@bot.command()
@bot.slash_command()
async def reload(ctx, extension):
    bot.reload_extension(f'cmds.{extension}')
    await ctx.respond(f'```Re - Loaded {extension} done.```')

for filename in os.listdir('./cmds'):
    if filename.endswith('.py'):
        bot.load_extension(f'cmds.{filename[:-3]}')

if __name__ == "__main__":
    bot.run(TOKEN) 
