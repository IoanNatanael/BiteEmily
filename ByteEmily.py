import asyncio
import os
import re
import discord
import mysql.connector
from discord.ext import commands
from dotenv import load_dotenv
import datetime


@commands.command()
async def your_command(ctx):
    await ctx.bot.wait_for(...)


load_dotenv()

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
countdown_count = 0

conn = None


def establish_connection():
    global conn
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USERNAME'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_DATABASE'),
            auth_plugin='mysql_native_password',
        )
    except mysql.connector.Error as err:
        print("Failed to establish MySQL connection:", err)


# noinspection PyUnresolvedReferences
def execute_non_query(query, values=None):
    global conn
    try:
        if conn.is_connected():
            cursor = conn.cursor()
            if values:
                cursor.execute(query, values)
            else:
                cursor.execute(query)
            conn.commit()
            cursor.close()
    except mysql.connector.Error as err:
        print("Failed to execute query:", err)


# noinspection PyUnresolvedReferences
def close_connection():
    global conn
    if conn is not None:
        conn.close()
        conn = None
    else:
        print("Connection is already closed or was never established.")


@bot.event
async def on_shutdown():
    close_connection()


def member_or_trial(user):
    member_role_name = 'member'
    trial_role_name = 'trial'
    lowercase_roles = [role.name.lower() for role in user.roles]
    return any(
        role_name == member_role_name.lower() or role_name == trial_role_name.lower() for role_name in lowercase_roles)


def format_with_hyphens(number):
    if number is None:
        return ""
    return "{:,}".format(number).replace(",", "-").replace(".", ",")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    establish_connection()

    close_connection()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"You are on cooldown. Try again in {error.retry_after:.2f}s")
    else:
        pass


async def handle_loot_bal_command(message):
    if not member_or_trial(message.author):
        await message.channel.send("You do not have permission to use this command.")
        return

    command_parts = message.content.split()
    if len(command_parts) != 2:
        await message.channel.send('Invalid command. Usage: !LootBal <playerName>')
        return

    playerName = command_parts[1].capitalize()

    cursor = None
    try:
        establish_connection()
        # noinspection PyUnresolvedReferences
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(Amount) FROM Transactions WHERE Player = %s", (playerName,))
        result = cursor.fetchone()

        if result is not None:
            total_amount = result[0]
            formatted_amount = format_with_hyphens(total_amount)
            if total_amount == 0 or total_amount is None:
                formatted_amount = "-0-"
            await message.channel.send(f'Player {playerName} has a total amount of {formatted_amount}')
        else:
            await message.channel.send('No results found.')

        cursor.fetchall()
    except Exception as e:
        await message.channel.send(f'An error occurred while retrieving the balance: {str(e)}')
    finally:
        if cursor is not None:
            cursor.close()
        close_connection()


@bot.command(name="LootBal")
async def lootbal(ctx, playerName: str):
    try:
        command_string = f"{playerName}"
        fake_message = ctx.message
        fake_message.content = f"!LootBal {command_string}"

        await handle_loot_bal_command(fake_message)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await ctx.send(error_message)


current_time = datetime.datetime.utcnow()


async def countdown_update(remaining_time, countdown_end_time, message, countdown_message, image_url, additional_text):
    while remaining_time.total_seconds() > 0:
        if remaining_time.total_seconds() <= 1800:
            update_interval = 5
        else:
            update_interval = 60

        await asyncio.sleep(update_interval)
        remaining_time = countdown_end_time - datetime.datetime.utcnow()

        if remaining_time.total_seconds() <= 0:
            countdown_content = f"`Objective is gone`.\n`Objective pop at`: {countdown_end_time.strftime('`%Y-%m-%d`  `%H:%M:%S')} UTC`"
        else:
            remaining_formatted = str(remaining_time)
            remaining_formatted = remaining_formatted.split(".")[0]
            countdown_content = f"Time remaining:```\n{remaining_formatted}\n```\n`Objective pop at`: {countdown_end_time.strftime('`%Y-%m-%d` `%H:%M:%S')} UTC`"

        try:
            if image_url:
                await countdown_message.edit(content=f"{countdown_content}\n{image_url}")
            else:
                await countdown_message.edit(content=countdown_content)
        except discord.NotFound:
            pass


# noinspection PyGlobalUndefined
async def handle_content_in_command(message):
    global countdown_count

    if countdown_count >= 30:
        await message.channel.send("Maximum countdown limit reached. You cannot create more countdowns.")
        return

    if not member_or_trial(message.author):
        print("User does not have permission to use this command.")

        await message.channel.send("You do not have permission to use this command.")
        return

    command_parts = message.content.split(" ")
    if len(command_parts) < 2:
        print("Invalid command format.")
        await message.channel.send("Invalid command format. Please use `!content_in <time> [image_url]`")
        return

    time_str = command_parts[1]
    time_units = {"min": "minutes", "hour": "hours", "day": "days"}

    if re.match(r"\d+:\d+:\d+", time_str):
        time_parts = time_str.split(":")
        if len(time_parts) != 3:
            await message.channel.send("Invalid time format. Please use `<number>:<number>:<number> (e.g., 1:20:30)`.")
            return

        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = int(time_parts[2])
        time_value = hours * 3600 + minutes * 60 + seconds

    elif re.match(r"\d+:\d+", time_str):
        time_parts = time_str.split(":")
        if len(time_parts) != 2:
            await message.channel.send("Invalid time format. Please use `<number>:<number> (e.g., 1:20).`")
            return

        minutes = int(time_parts[0])
        seconds = int(time_parts[1])
        time_value = minutes * 60 + seconds
    else:
        try:
            time_value = int(time_str)
        except ValueError:
            await message.channel.send(
                "Invalid time format. Please use `<number>, <number>:<number>`, or `<number>:<number>:<number> (e.g., 1, 1:20, or 1:20:30)`")
            return

    image_url = None
    additional_text = ""
    countdown_count += 1

    if len(command_parts) > 2:
        if command_parts[-1].startswith("http"):
            image_url = command_parts[-1]
            additional_text = " ".join(command_parts[2:-1])
        else:
            additional_text = " ".join(command_parts[2:])

    end_time = current_time + datetime.timedelta(seconds=time_value)
    remaining_time = end_time - current_time

    remaining_formatted = str(remaining_time)
    remaining_formatted = remaining_formatted.split(".")[0]
    countdown_content = f"Time remaining:```\n{remaining_formatted}\n```\n`Counting will end at:` {end_time.strftime('`%Y-%m-%d` `%H:%M:%S')} UTC`"

    if image_url:
        countdown_message = await message.reply(f"{countdown_content}\n{image_url}")
    else:
        countdown_message = await message.reply(countdown_content)
    await countdown_message.add_reaction("❌")

    def check_reaction(reaction, user):
        return str(reaction.emoji) == "❌" and reaction.message.id == countdown_message.id and (
                user == message.author or discord.utils.get(user.roles, name="Guild Master"))

    countdown_task = asyncio.create_task(
        countdown_update(remaining_time, end_time, message, countdown_message, image_url, additional_text))

    try:
        reaction, _ = await bot.wait_for("reaction_add", check=check_reaction, timeout=86400)
    except asyncio.TimeoutError:
        pass

    else:
        if str(reaction.emoji) == "❌":
            countdown_task.cancel()
            try:
                await countdown_message.delete()
            except discord.NotFound:
                print("Countdown message not found...")


@bot.command()
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def content_in(ctx, time_str: str, *args):
    if ctx.channel.id != 1005640291937697872:
        return
    try:
        await handle_content_in_command(ctx.message)
    except ValueError:
        error_message = "Invalid time format. Please use <number>, <number>:<number>, or <number>:<number>:<number> (e.g., 1, 1:20, or 1:20:30)."
        await ctx.send(error_message)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await ctx.send(error_message)


@bot.command()
async def info(ctx):
    try:

        embed = discord.Embed(
            title="Command Information",
            description="List of available commands and their explanations:",
            color=discord.Color.gold(),
        )

        command_s = [
            {
                "name": "**!content_in**",
                "description": " -----------------------------------------------------------------------"
                               "**-Set a countdown** for a specified duration. -----------------------------------------"
                               "-It also shows the final time when the content should happen. -----------"
                               "----------You can also add any text and an image in the message if you want. ----------------"
                               "And you can delete the message by using the '❌' emoji---------------------------"
                               "-The time format is {hh:mm:ss}.",
                "usage": "!content_in <time> [image_url] [additional_text]"
            },
            {
                "name": "**!LootBal**",
                "description": "**Retrieves** the balance amount of the specified player.",
                "usage": "!LootBal <playerName>"
            }
        ]

        for command in command_s:
            embed.add_field(
                name=f"☆•☆ {command['name']}",
                value=f"Description: {command['description']}\nUsage: `{command['usage']}`\n{'-' * 80}",
                inline=False
            )

        await ctx.send(embed=embed)
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await ctx.send(error_message)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    establish_connection()


# noinspection PyUnresolvedReferences
def main():
    try:
        bot.run(os.getenv('BOT_TOKEN'))
    except KeyboardInterrupt:
        print('Bot stopped.')
        bot.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
