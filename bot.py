from re import findall
from dotenv import load_dotenv
from classes import Game
import engine_interface as ei

import os
import discord
import pyffish as sf

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
BOT_NAME = os.getenv('BOT_NAME')
ENGINE_LOCATION = os.getenv('ENGINE_LOCATION')
VARIANTS_LOCATION = os.getenv('VARIANTS_LOCATION')
MOVETIME = int(os.getenv('ENGINE_MOVETIME'))

client = discord.Client(activity=discord.Game(name='--help'))
games_dict = {} # channelid: game info
bot_playing_in = {} # channelid: bot skill level

with open(VARIANTS_LOCATION, "r") as f:
    ini_text='\n'.join(f.readlines())
sf.load_variant_config(ini_text)

allowed_variants = ['chess', 'checklesszh', 'racingchess', 'dragonfly', 'shinobimirror',
                    'chennis', 'extinction', 'mounted', 'twokings', 'pandemonium', 'chak']


async def game_over(message, result):
    game = games_dict[message.channel.id]

    if result == "White":
        result_text = f"{game.wplayer} wins."
        result_code = "1-0"
    elif result == "Black":
        result_text = f"{game.bplayer} wins."
        result_code = "0-1"
    elif result == "Draw":
        result_text = "Draw."
        result_code = "1/2-1/2"
        
    await message.channel.send("**GAME OVER**"
                                f"\nResult: {result_text}"
                                f"\nGame moves: {' '.join(game.get_moves() + [result_code])}"
                                f"\n*(Game lasted {game.age_minutes()} minutes.)*"
                                )
    
    del games_dict[message.channel.id]
    return


async def bot_makes_move(message):
    game = games_dict[message.channel.id]

    engine = ei.open_engine(ENGINE_LOCATION)
    ei.put(engine, f"load {VARIANTS_LOCATION}")
    ei.put(engine, f"setoption name UCI_Variant value {game.variant}")
    ei.put(engine, f"setoption name Skill Level value {bot_playing_in[message.channel.id]}")
    ei.put(engine, f"position startpos moves {' '.join(game.moves)}")
    ei.put(engine, f"go movetime {MOVETIME}")

    # Get engine output    
    std_output = []
    while True:
        if std_output:                    
            bestmove_found = findall('bestmove .+', std_output[-1])
            if bestmove_found: 
                bestmove = bestmove_found[0].split()[1]
                engine_eval = findall("(?:cp|mate) [-]?\d+", ''.join(std_output))[-1]
                break
        std_output += ei.get(engine)

    ei.put(engine, "quit")

    await message.channel.send(f"--m {sf.get_san(game.variant, game.fen, bestmove)}"
                               f"\nEngine eval: **{engine_eval}**"
                               )
    return


@client.event
async def on_ready():
    guilds = await client.fetch_guilds(limit=150).flatten()
    print(f"{client.user} is connected to the following guilds:")
    for guild in guilds:
        print(f"{guild.name} [{guild.id}]")
    print()


@client.event
async def on_message(message):
    message_text = str(message.content)
    username = str(message.author)
    game = games_dict.get(message.channel.id, None)
    
    if message_text == '--help':
        await message.channel.send("**Commands:**"
                                   "\n--fen [variant] [fen] (displays a FEN)"
                                   "\n--game [variant] [@opponent] [white/black] (start a game)"
                                   "\n--move"
                                   "\n--display (displays position information)"
                                   "\n--offerdraw"
                                   "\n--acceptdraw"
                                   "\n--resign"
                                   "\n--asktakeback"
                                   "\n--accepttakeback"
                                   "\nAliases: --g, --m, --d, --od, --ad --tb, --atb"
                                   "\n\n**Available variants:** \n" + (', ').join(allowed_variants)
                                   )
        return

    if message_text.startswith('--fen '):
        variant = message_text.split()[1]
        input_fen = ' '.join(message_text.split()[2:])

        if variant not in allowed_variants:
            await message.channel.send("Variant not recognized.")
            return
        
        if sf.validate_fen(input_fen, "chess") != sf.FEN_OK:
            await message.channel.send("Invalid FEN.")
            return

        position = Game(variant)
        position.fen = sf.get_fen(variant, input_fen, [])
        
        img_name = 'fen_' + str(message.channel.id) + '.png'

        await message.channel.send("**POSITION DISPLAY**")
        await message.channel.send(file=discord.File(position.render(img_name)))
        
        output = (f"It's **{position.turn()}** to move."
                  f"\nFEN: {position.fen}")

        if variant == 'chess':
            analysis_link = 'https://lichess.org/analysis/standard/' + position.fen.replace(' ', '_')
            output += f"\nAnalyze position: {analysis_link}"
        
        await message.channel.send(output)
        del position
        return
        
    if message_text.startswith('--game ') or message_text.startswith('--g '):
        # Check if game can be created
        if game:
            await message.channel.send("There is already a game going on!")
            return

        try:
            opponent = str(await client.fetch_user(int(findall("\d+", message_text.split()[2])[0])))
        except:
            await message.channel.send("Opponent not found.")
            return
        
        variant = message_text.split()[1]
        if variant not in allowed_variants:
            await message.channel.send("Variant not recognized.")
            return

        # Create game
        if 'black' in message_text.split():
            games_dict[message.channel.id] = Game(variant, opponent, username)
        else:
            games_dict[message.channel.id] = Game(variant, username, opponent)
        
        game = games_dict[message.channel.id]

        # Set bot skill
        if game.player_is_playing(BOT_NAME):
            if findall('skill=(-?\d+)', message_text):
                level = int(findall('skill=(-?\d+)', message_text)[0])
                if level > 20 or level < -20:
                    level = 20
            else:
                level = 0
            bot_playing_in[message.channel.id] = level

        # Create image
        img_name = 'board_' + str(message.channel.id) + '.png'
        await message.channel.send(f"Game started of: **{variant}**"
                                   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**"
                                   )
        await message.channel.send(file=discord.File(game.render(img_name)))

        if game.player_turn(BOT_NAME):
            await bot_makes_move(message)
            
        return

    if message_text.startswith('--move ') or message_text.startswith('--m '):
        if not game:
            await message.channel.send("No game is active.")
            return
            
        if (username == game.wplayer and game.turn() == "White") or (username == game.bplayer and game.turn() == "Black"):
            move = game.closest_san(message_text.split()[1])
            
            if move:
                game.make_move(move)
                result = game.ended()
                turn = game.turn()

                if result:
                    if (result == "Win" and turn == "White") or (result == "Loss" and turn == "Black"):
                        await game_over(message, "White")
                        
                    elif (result == "Win" and turn == "Black") or (result == "Loss" and turn == "White"):
                        await game_over(message, "Black")
                        
                    elif result == "Draw":
                        await game_over(message, "Draw")

                else:
                    await message.channel.send(f"Made move: **{game.get_moves()[-1]}**"
                                               f"\nIt's **{game.turn()}** to move."
                                               )
                
                img_name = 'board_' + str(message.channel.id) + '.png'
                await message.channel.send(file=discord.File(game.render(img_name)))

                if game.player_turn(BOT_NAME) and not result:
                    await bot_makes_move(message)
                return
            
            await message.channel.send("Invalid move.")
            return
        
        await message.channel.send("It's not your turn!")
        return

    if message_text in ('--display', '--d'):
        if not game:
            await message.channel.send("No game is active.")
            return
        img_name = 'board_' + str(message.channel.id) + '.png'
        await message.channel.send(file=discord.File(game.render(img_name)))
        await message.channel.send(f"Variant: **{game.variant}**"
                                   f"\nPosition: {game.fen}"
                                   f"\nMoves so far: {' '.join(game.get_moves())}"
                                   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**"
                                   f"\nIt's **{game.turn()}** to move."
                                   f"\nLegal moves: {' '.join(game.legal_moves())}"
                                   f"\n*(Game started {game.age_minutes()} minutes ago.)*"
                                   )
        return

    if message_text == '--resign':
        if not game:
            await message.channel.send("No game is active.")
            return 
        if username == game.wplayer:
            await game_over(message, "Black")
            return
        if username == game.bplayer:
            await game_over(message, "White")
            return
        await message.channel.send("You're not playing!")
        return

    if message_text in ('--offerdraw', '--od'):
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username == game.wplayer:
            if not game.w_offered_draw:
                game.w_offered_draw = True
                await message.channel.send("White offers a draw!")

                if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                    await message.channel.send("--ad")
                    
                return
            await message.channel.send("You already offered a draw.")
            return
        
        if username == game.bplayer:
            if not game.b_offered_draw:
                game.b_offered_draw = True
                await message.channel.send("Black offers a draw!")

                if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                    await message.channel.send("--ad")
                    
                return
            await message.channel.send("You already offered a draw.")
            return
        
        await message.channel.send("You're not playing!")
        return

    if message_text in ('--acceptdraw', '--ad'):
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username not in (game.wplayer, game.bplayer):
            await message.channel.send("You're not playing!")
            return
            
        if username == game.wplayer and game.b_offered_draw:
            await message.channel.send("White accepted the draw offer!")
            await game_over(message, "Draw")
            return
        
        if username == game.bplayer and game.w_offered_draw:
            await message.channel.send("Black accepted the draw offer!")
            await game_over(message, "Draw")
            return
        
        await message.channel.send("No draw offers active.")
        return

    if message_text in ('--asktakeback', '--tb'):
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username == game.wplayer:
            if not game.w_offered_takeback:
                game.w_offered_takeback = True
                await message.channel.send("White asks for a takeback!")

                if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                    await message.channel.send("--atb")
                    
                return
            await message.channel.send("You already offered a takeback.")
            return
        
        if username == game.bplayer:
            if not game.b_offered_takeback:
                game.b_offered_takeback = True
                await message.channel.send("Black asks for a takeback!")

                if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                    await message.channel.send("--atb")
                    
                return
            await message.channel.send("You already offered a takeback.")
            return
        
        await message.channel.send("You're not playing!")
        return

    if message_text in ('--accepttakeback', '--atb'):
        if not game:
            await message.channel.send("No game is active.")
            return
        
        if username not in (game.wplayer, game.bplayer):
            await message.channel.send("You're not playing!")
            return
            
        if username == game.wplayer and game.b_offered_takeback:
            await message.channel.send("White has granted a takeback: the last two moves have been undone.")
            game.takeback_move()
            return
        
        if username == game.bplayer and game.w_offered_takeback:
            await message.channel.send("Black has granted a takeback: the last two moves have been undone.")
            game.takeback_move()
            return
        
        await message.channel.send("No takeback requests active.")
        return

    if client.user.mentioned_in(message):
        await message.channel.send("hello! :)")
    

@client.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as log:
        if event == 'on_message':
            log.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

client.run(TOKEN)
