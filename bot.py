# bot.py

import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands

from contract_scanner import scan_contracts
from esi_auth import close_session

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
        print(f"Sync error: {e}")


@bot.tree.command(name="contracts", description="Scan Aldranette corp contracts for ships.")
async def contracts(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    # Run the heavy scan in the event loop (already async & non‑blocking)
    try:
        ships, total = await scan_contracts()
    except Exception as e:
        await interaction.followup.send(f"Error while scanning contracts: `{e}`")
        return

    if not ships:
        await interaction.followup.send(
            f"No ships found on outstanding contracts in Aldranette.\nTotal contracts: {total}"
        )
        return

    # Build a compact message
    lines = [f"**Ships on contracts in Aldranette:**", ""]
    for name, count in sorted(ships.items()):
        lines.append(f"**{name}** — {count}")

    lines.append("")
    lines.append(f"Total contracts: {total}")

    # Discord message limit safety
    msg = "\n".join(lines)
    if len(msg) > 1900:
        # Truncate if insane, or split into chunks if you prefer
        msg = msg[:1900] + "\n...(truncated)"

    await interaction.followup.send(msg)


async def main():
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # Cleanly close aiohttp session on shutdown
        asyncio.run(close_session())
