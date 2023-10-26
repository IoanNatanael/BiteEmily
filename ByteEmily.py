import asyncio
import os
import discord
import mysql.connector
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import pytz


# Define a custom command
@commands.command()
async def your_command(ctx):
    await ctx.bot.wait_for(...)  # Placeholder for command logic


# Load environment variables from a .env file
load_dotenv()

# Initialize Discord bot with specified intents
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
countdown_count = 0  # Counter for countdown commands

conn = None  # Global variable for database connection


# Function to establish a connection to the MySQL database
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


# Function to execute a non-query SQL command
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


# Function to close the database connection
# noinspection PyUnresolvedReferences
def close_connection():
    global conn
    if conn is not None:
        conn.close()
        conn = None
    else:
        print("Connection is already closed or was never established.")


# Event handler when the bot is shutting down
@bot.event
async def on_shutdown():
    close_connection()


# Function to check if a user has a specific role
def member_or_trial(user):
    member_role_name = 'member'
    trial_role_name = 'trial'
    lowercase_roles = [role.name.lower() for role in user.roles]
    return any(
        role_name == member_role_name.lower() or role_name == trial_role_name.lower() for role_name in lowercase_roles)


# Function to format a number with hyphens for display
def format_with_hyphens(number):
    if number is None:
        return ""
    return "{:,}".format(number).replace(",", "-").replace(".", ",")


@bot.event
async def on_reaction_add(reaction, user):
    # Check if the reaction is "❌" and the user is not a bot
    if str(reaction.emoji) == "❌" and not user.bot:
        try:
            # Fetch the message to make sure it still exists
            original_message = await reaction.message.channel.fetch_message(reaction.message.id)
            # Delete the original message
            await original_message.delete()
        except discord.NotFound:
            # Handle the case where the message does not exist anymore
            print("Message not found, could not delete.")


# Event handler when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    establish_connection()  # Establish database connection

    close_connection()  # Close database connection


# Function to handle the !LootBal command
# noinspection PyUnresolvedReferences
async def handle_loot_bal_command(message):
    # Check if the user has necessary permissions
    if not member_or_trial(message.author):
        await message.channel.send("You do not have permission to use this command.")
        return

    command_parts = message.content.split()
    # Validate command syntax
    if len(command_parts) != 2:
        await message.channel.send('Invalid command. Usage: !LootBal <playerName>')
        return

    playerName = command_parts[1].capitalize()

    cursor = None
    try:
        establish_connection()  # Establish database connection
        cursor = conn.cursor()

        # Execute SQL query to retrieve total amount for the specified player
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
            cursor.close()  # Close database cursor
        close_connection()  # Close database connection


# Command decorator for !LootBal command
@bot.command(name="LootBal")
async def lootbal(ctx, playerName: str):
    try:
        command_string = f"{playerName}"
        fake_message = ctx.message
        fake_message.content = f"!LootBal {command_string}"

        await handle_loot_bal_command(fake_message)  # Call the handle_loot_bal_command function
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await ctx.send(error_message)  # Send error message to the channel


@bot.command()
async def content_in(ctx, time_str: str):
    if ctx.channel.id != 1005640291937697872: 
        pass
    try:
        # Parse input time (hours:minutes)
        hours, minutes = map(int, time_str.split(':'))
        total_seconds = hours * 3600 + minutes * 60

        # Calculate end time in UTC
        current_time = datetime.datetime.utcnow()
        end_time = current_time + datetime.timedelta(seconds=total_seconds)

        # Format countdown message using Discord timestamp format
        utc = pytz.timezone('UTC')
        end_time_utc = utc.localize(end_time)
        discord_timestamp = f'<t:{int(end_time_utc.timestamp())}:R>'
        formatted_time = end_time_utc.strftime('%Y-%m-%d `%H:%M:%S`')
        countdown_message = f"Countdown will end at: {discord_timestamp} ({formatted_time} UTC)"

        # Reply to the user's message with the countdown message
        response_message = await ctx.message.reply(countdown_message)

        # Add "❌" emoji reaction to the response message
        await response_message.add_reaction("❌")

        def check_reaction(reaction, user):
            return str(reaction.emoji) == "❌" and reaction.message.id == response_message.id and user == ctx.author

        # Wait for the countdown to finish or until user reacts with "❌" emoji
        while end_time > datetime.datetime.utcnow():
            await asyncio.sleep(1)

            try:
                reaction, _ = await bot.wait_for("reaction_add", check=check_reaction, timeout=1)
                # User reacted with "❌", stop the countdown
                break
            except asyncio.TimeoutError:
                pass

        # Edit the original countdown message when countdown is done
        await response_message.edit(content="Content ended!")

    except Exception as e:
        await ctx.message.reply(f"Error occurred: {str(e)}")


# Command to provide information about available commands
@bot.command()
async def info_emily(ctx):
    try:
        # Create an embed for command information
        embed = discord.Embed(
            title="Command Information",
            description="List of available commands and their explanations:",
            color=discord.Color.gold(),
        )

        # List of command descriptions and usage instructions
        command_s = [
            {
                "name": "**!content_in**",
                "description": " -----------------------------------------------------------------------"
                               "-**Set a countdown** for a specified duration. -----------------------------------------"
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

        # Add fields to the embed for each command
        for command in command_s:
            embed.add_field(
                name=f"☆•☆ {command['name']}",
                value=f"Description: {command['description']}\nUsage: `{command['usage']}`\n{'-' * 80}",
                inline=False
            )

        await ctx.send(embed=embed)  # Send the embed to the channel
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        await ctx.send(error_message)  # Send error message to the channel


bot_latency = bot.latency  # Get bot latency
print(f"Bot latency: {bot_latency} seconds")  # Print bot latency in seconds


# Main function to run the bot
# noinspection PyUnresolvedReferences
def main():
    try:
        bot.run(os.getenv('BOT_TOKEN2'))  # Run the bot with the provided token
    except KeyboardInterrupt:
        print('Bot stopped.')
        bot.close()
        if conn:
            conn.close()  # Close database connection if open


if __name__ == "__main__":
    main()  # Call the main function if the script is executed directly
