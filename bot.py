from gen_board import render_board
from re import findall
from dotenv import load_dotenv
from classes import Game

import os
import discord
import pyffish as sf

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

client = discord.Client(activity=discord.Game(name='try --help'))
games_dict = {}

with open("variantsfile.txt", "r") as f:
    ini_text='\n'.join(f.readlines())
    
sf.load_variant_config(ini_text)

allowed_variants = ['chess', 'crazyhouse', 'grand', 'chennis', 'extinction', 'ridgerelay']


async def game_over(message, winner, moves, result):
    del games_dict[message.channel.id]
    
    if winner:
        await message.channel.send("**GAME OVER**" +
                                   f"\nResult: **{winner}** wins." +
                                   f"\nGame moves: {' '.join(moves)} {result}"
                                   )
        return
    
    await message.channel.send("**GAME OVER**" +
                               f"\nResult: Draw." +
                               f"\nGame moves: {' '.join(moves)} {result}"
                               )
    return


@client.event
async def on_ready():
    guilds = await client.fetch_guilds(limit=150).flatten()
    print(f"{client.user} is connected to the following guilds:")
    for guild in guilds:
        print(f"{guild.name} [{guild.id}]")
    print('')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    message_text = str(message.content)
    username = str(message.author)
    game = games_dict.get(message.channel.id, None)
    
    if message_text == '--help':
        await message.channel.send("**Commands:** \n--game [variant] [@opponent] (start a game, you play as white)\n--move\n--display (displays position information)\n--resign\n--offerdraw\n--acceptdraw")
        return

    if message_text.startswith('--game '):
        try:
            opponent = await client.fetch_user(int(message_text.split()[2][3:-1]))
        except:
            await message.channel.send("Opponent not found.")
            return
        
        if game:
            await message.channel.send("There is already a game going on!")
            return
        
        variant = message_text.split()[1]

        if variant not in allowed_variants:
            await message.channel.send(f"**Available variants:** " + ' '.join(allowed_variants))
            return

        games_dict[message.channel.id] = Game(str(message.channel.id), username, str(opponent), variant, [])
        game = games_dict[message.channel.id]
        img_name = 'board_' + str(message.channel.id) + '.png'
        await message.channel.send(f"Game started of: **{variant}**")
        await message.channel.send(file=discord.File(game.render(img_name)))
        return

    if message_text.startswith('--move '):
        if not game:
            await message.channel.send("No game is active.")
            return
            
        if (username == game.wplayer and game.turn() == "White") or (username == game.bplayer and game.turn() == "Black"):
            move = message_text.split()[1]

            if move in game.legal_moves():
                games_dict[message.channel.id].make_move(move)
                
                if (game.ended() == "Win" and game.turn() == "White") or (game.ended() == "Loss" and game.turn() == "Black"):
                    await game_over(message, game.wplayer, game.get_moves(), "1-0")
                    
                elif (game.ended() == "Win" and game.turn() == "Black") or (game.ended() == "Loss" and game.turn() == "White"):
                    await game_over(message, game.bplayer, game.get_moves(), "0-1")
                    
                elif game.ended() == "Draw":
                    await game_over(message, None, game.get_moves(), "1/2-1/2")

                else:
                    await message.channel.send(f"Made move: **{move}**" +
                                               f"\nIt's **{game.turn()}** to move."
                                               )
                
                img_name = 'board_' + str(message.channel.id) + '.png'
                await message.channel.send(file=discord.File(game.render(img_name)))
                return
            
            await message.channel.send("Not a legal move.")
            return
        
        await message.channel.send("It's not your turn!")
        return

    if message_text == '--display':
        if not game:
            await message.channel.send("No game is active.")
            return
        img_name = 'board_' + str(message.channel.id) + '.png'
        await message.channel.send(file=discord.File(game.render(img_name)))
        await message.channel.send(f"Variant: **{game.variant}**" +
                                   f"\nPosition: {game.fen()}" +
                                   f"\nMoves so far: {' '.join(game.get_moves())}" +
                                   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**" +
                                   f"\nIt's **{game.turn()}** to move." +
                                   f"\nLegal moves: {' '.join(game.legal_moves())}" +
                                   f"\n*(Game started {game.age_minutes()} minutes ago.)*"
                                   )
        return

    if message_text == '--resign':
        if not game:
            await message.channel.send("No game is active.")
            return 
        if username == game.wplayer:
            await game_over(message, game.bplayer, game.get_moves(), "0-1")
            return
        if username == game.bplayer:
            await game_over(message, game.wplayer, game.get_moves(), "1-0")
            return
        await message.channel.send("You're not playing!")
        return

    if message_text == '--offerdraw':
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username == game.wplayer:
            if not games_dict[message.channel.id].w_offered_draw:
                games_dict[message.channel.id].w_offered_draw = True
                await message.channel.send("White offers a draw!")
                return
            await message.channel.send("You already offered a draw.")
            return
        
        if username == game.bplayer:
            if not games_dict[message.channel.id].b_offered_draw:
                games_dict[message.channel.id].b_offered_draw = True
                await message.channel.send("Black offers a draw!")
                return
            await message.channel.send("You already offered a draw.")
            return
        
        await message.channel.send("You're not playing!")
        return

    if message_text == '--acceptdraw':
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username not in (game.wplayer, game.bplayer):
            await message.channel.send("You're not playing!")
            return
            
        if username == game.wplayer and games_dict[message.channel.id].b_offered_draw:
            await message.channel.send("White accepted the draw offer!")
            await game_over(message, None, game.get_moves(), "1/2-1/2")
            return
        
        if username == game.bplayer and games_dict[message.channel.id].w_offered_draw:
            await message.channel.send("Black accepted the draw offer!")
            await game_over(message, None, game.get_moves(), "1/2-1/2")
            return
        
        await message.channel.send("No draw offers active.")
        return

@client.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as log:
        if event == 'on_message':
            log.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

client.run(TOKEN)
