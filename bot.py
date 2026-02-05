# bot.py

import discord
from discord import app_commands
from discord.ext import commands

from contract_scanner import scan_contracts

import os
TOKEN = os.getenv("DISCORD_TOKEN")


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)


@bot.tree.command(name="contracts", description="Scan Aldranette corp contracts for ships.")
async def contracts(interaction: discord.Interaction):
    await interaction.response.defer()

    ships, total = scan_contracts()

    if not ships:
        await interaction.followup.send(
            f"No ships found on outstanding contracts in Aldranette.\nTotal contracts: {total}"
        )
        return

    lines = [f"**Ships on contracts in Aldranette:**", ""]
    for name, count in sorted(ships.items()):
        lines.append(f"**{name}** — {count}")

    lines.append("")
    lines.append(f"Total contracts: {total}")

    await interaction.followup.send("\n".join(lines))


bot.run(TOKEN)
