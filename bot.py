import os
import discord
import pyffish as sf
from tinydb import TinyDB, Query
from re import findall
from dotenv import load_dotenv
from random import randint
from asyncio import sleep

from game import Game
from engine import Engine


load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
BOT_NAME = os.getenv('BOT_NAME')
ADMIN_NAME = os.getenv('ADMIN_NAME')
ENGINE_LOCATION = os.getenv('ENGINE_LOCATION')
VARIANTS_LOCATION = os.getenv('VARIANTS_LOCATION')
MOVETIME = int(os.getenv('ENGINE_MOVETIME'))

client = discord.Client(activity=discord.Game(name='--help'))
games_dict = {} # {channelid: game info}

with open(VARIANTS_LOCATION, "r") as f:
    ini_text='\n'.join(f.readlines())
sf.load_variant_config(ini_text)

allowed_variants = ['chess', 'checklesszh', 'racingchess', 'dragonfly', 'shinobimirror',
                    'chennis', 'extinction', 'mounted', 'twokings', 'pandemonium', 'chak']

db = TinyDB('saved_games.json')
for game_records in db: # only 1 entry in DB
    for channel in game_records:
        game = Game()
        game.__dict__ = game_records[channel]
        games_dict[int(channel)] = game


async def game_over(message, result):
    game = games_dict[message.channel.id]

    result_text, result_code = {'White': (f"{game.wplayer} wins.", "1-0"),
                                'Black': (f"{game.bplayer} wins.", "0-1"),
                                'Draw': ("Draw.", "1/2-1/2")
                                }[result]

    output = ("**GAME OVER**"
              f"\nResult: {result_text}"
              f"{f'{chr(10)}Custom start position: **{game.startpos}**' if game.custom_fen else ''}"
              f"\nGame moves: {' '.join(game.get_moves() + [result_code])}"
              f"\n*(Game lasted {game.age_minutes()} minutes.)*")
    
    await message.channel.send(output)
    await display_board(message, game, prefix='board_')
    
    del games_dict[message.channel.id]
    return


async def bot_makes_move(message):
    game = games_dict[message.channel.id]

    # Get a best move from Fairy-Stockfish
    engine = Engine(ENGINE_LOCATION, VARIANTS_LOCATION, game.variant, game.bot_skill) 
    bestmove, engine_eval = engine.analyze(game.startpos, game.moves, MOVETIME)
    engine.quit()
    
    mating_line = engine_eval.split()[0] == 'mate' and -3 <= int(engine_eval.split()[1]) <= -1
    cp_losing = engine_eval.split()[0] == 'cp' and int(engine_eval.split()[1]) <= 50*game.bot_skill - 1500
    # cp_losing threshold depends on skill, from -500 at max skill to -2500 at min skill

    if mating_line or cp_losing:
        await message.channel.send(f"Alas, I have been bested :(")
        await message.channel.send("--resign") 
        return
    
    await message.channel.send(f"--m {sf.get_san(game.variant, game.fen, bestmove)} ||**{engine_eval}**||")
    return


async def display_board(message, game_object, prefix):
    img_name = prefix + str(message.channel.id) + '.png'
    await message.channel.send(file=discord.File(game_object.render(img_name)))
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
        output = ("**Commands:**"
                  "\n--fen [variant] [fen] (displays a FEN)"
                  "\n--game [variant] [@opponent] [white/black] [fen='{fen}'] [skill=(-20,20)] (starts a game)"
                  "\n--move"
                  "\n--premove"
                  "\n--display (displays position information)"
                  "\n--offerdraw"
                  "\n--acceptdraw"
                  "\n--resign"
                  "\n--asktakeback"
                  "\n--accepttakeback"
                  "\nAliases: --g, --m, --pm, --d, --od, --ad --tb, --atb"
                  "\n\n**Available variants:** \n" + (', ').join(allowed_variants))
        
        await message.channel.send(output)
        return

    if message_text.startswith('--fen '):
        variant = message_text.split()[1]
        input_fen = ' '.join(message_text.split()[2:])

        # Validate FEN
        if variant not in allowed_variants:
            await message.channel.send("Variant not recognized.")
            return
        
        if sf.validate_fen(input_fen, variant) != sf.FEN_OK:
            await message.channel.send("Invalid FEN.")
            return

        # Create a dummy game
        position = Game(variant)
        position.fen = sf.get_fen(variant, input_fen, [])
        
        await message.channel.send("**POSITION DISPLAY**")
        await display_board(message, position, prefix='fen_')
        
        output = (f"It's **{position.turn()}** to move."
                  f"\nFEN: {position.fen}")

        # Link to Lichess analysis board
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

        # Custom starting position
        fen_search = findall("fen=[\"|\']([^\"\']*)[\"|\']", message_text)
        if fen_search:
            input_fen = fen_search[0]       
            if sf.validate_fen(input_fen, variant) == sf.FEN_OK:
                start_fen = sf.get_fen(variant, input_fen, [])
            else:
                await message.channel.send("Invalid FEN.")
                return
        else:
            start_fen = None

        # Create game
        # if side is not specified, choose randomly
        if 'white' in message_text.split():
            games_dict[message.channel.id] = Game(variant, username, opponent, start_fen) # play white       
        elif 'black' in message_text.split():
            games_dict[message.channel.id] = Game(variant, opponent, username, start_fen) # play black
        elif randint(0, 1):
            games_dict[message.channel.id] = Game(variant, username, opponent, start_fen) # play white
        else:
            games_dict[message.channel.id] = Game(variant, opponent, username, start_fen) # play black
            
        game = games_dict[message.channel.id]

        # Set bot skill (default 0)
        if game.player_is_playing(BOT_NAME):
            skill_search = findall('skill=(-?\d+)', message_text)
            if skill_search:
                game.bot_skill = max(min(int(skill_search[0]), 20), -20) # level must be -20 to 20
            
        # Send image
        await message.channel.send(f"Game started of: **{variant}**"
                                   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**")
        await display_board(message, game, prefix='board_')

        if game.player_turn(BOT_NAME):
            await bot_makes_move(message)
        return

    if message_text.startswith('--move ') or message_text.startswith('--m '):
        # Check if move can be made
        if not game:
            await message.channel.send("No game is active.")
            return
            
        if not game.player_turn(username):
            await message.channel.send("It's not your turn!")
            return
        
        move = game.closest_san(message_text.split()[1])
        if not move:
            await message.channel.send("Invalid move.")
            return
            
        game.make_move(move)

        # Check if game has ended
        if game.ended():
            await game_over(message, game.ended())
            return

        await message.channel.send(f"**{game.turn(opposite=True)}** made move: **{move}**")

        # Execute premove
        if game.premove:
            premove = game.closest_san(game.premove)

            # Check if premove can be made
            if not premove:
                await message.channel.send("Premove not made.")
            else:            
                game.make_move(premove)
                if game.ended():
                    await game_over(message, game.ended())
                    return
                await message.channel.send(f"**{game.turn(opposite=True)}** premoved: {premove}")

            game.premove = None

        await display_board(message, game, prefix='board_')

        # Bot move (bot doesn't premove)
        if game.player_turn(BOT_NAME):
            await bot_makes_move(message)
        return

    if message_text.startswith('--premove') or message_text.startswith('--pm'):
        await sleep(2) # otherwise stuff breaks

        # Check if premove can be made
        if not game:
            await message.channel.send("No game is active.")
            return
            
        if not game.player_turn(username, opposite=True): # premove can only be made on your opponent's turn
            await message.channel.send("Cannot make premove.")
            return

        if message_text in ('--premove', '--pm'): # if no premove is given
            game.premove = None
            await message.channel.send("Cleared premove.")
            return
        
        premove = message_text.split()[1]
        game.premove = premove

        await message.channel.send("Set premove.")
        return
    
    if message_text in ('--display', '--d'):
        if not game:
            await message.channel.send("No game is active.")
            return
        
        output = (f"Variant: **{game.variant}**"
                  f"{f'{chr(10)}Custom start: **{game.startpos}**' if game.custom_fen else ''}"
                  f"\nPosition: **{game.fen}**"
                  f"\nMoves so far: {' '.join(game.get_moves())}"
                  f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**"
                  f"\nIt's **{game.turn()}** to move."
                  f"\nLegal moves: {' '.join(game.legal_moves())}"
                  f"\n*(Game started {game.age_minutes()} minutes ago.)*")

        await display_board(message, game, prefix='board_')
        await message.channel.send(output)
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
            if game.w_offered_draw:
                await message.channel.send("You already offered a draw.")
                return
            
            game.w_offered_draw = True
            await message.channel.send("White offers a draw!")

            if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                await sleep(1)
                await message.channel.send("--ad")
                    
            return
            
        if username == game.bplayer:
            if game.b_offered_draw:
                await message.channel.send("You already offered a draw.")
                return
            
            game.b_offered_draw = True
            await message.channel.send("Black offers a draw!")

            if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                await message.channel.send("--ad")
                    
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
            if game.w_offered_takeback:
                await message.channel.send("You already offered a takeback.")
                return
            
            game.w_offered_takeback = True
            await message.channel.send("White asks for a takeback!")

            if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                await sleep(1)
                await message.channel.send("--atb")
                    
            return
        
        if username == game.bplayer:
            if game.b_offered_takeback:
                await message.channel.send("You already offered a takeback.")
                return
            
            game.b_offered_takeback = True
            await message.channel.send("Black asks for a takeback!")

            if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
                await message.channel.send("--atb")
                    
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

    if message_text == '--eval':
        # Get a best move from Fairy-Stockfish
        engine = Engine(ENGINE_LOCATION, VARIANTS_LOCATION, game.variant, game.bot_skill)
        if username == ADMIN_NAME: # admins get more stockfish power :)
            engine.allocate(threads=11, memory=256)
            engine_eval = engine.analyze(game.startpos, game.moves, MOVETIME*10)[1]
        else:
            engine_eval = engine.analyze(game.startpos, game.moves, MOVETIME)[1]
        engine.quit()
        await message.channel.send(f"Position eval: ||**{engine_eval}**||")
        return

    # Admin commands
    if message_text == '--save' and username == ADMIN_NAME:
        db.truncate()
        db.insert({key: games_dict[key].__dict__ for key in games_dict}) # convert games to dict
        await message.channel.send("Saved current games.")
        return         

    if message_text == '--repr' and username == ADMIN_NAME:
        if game:
            await message.channel.send(game.__dict__)
        return

    if client.user.mentioned_in(message) and message.author != client.user:
        await message.channel.send("hello! :)")
        return
    

@client.event
async def on_error(event, *args, **kwargs):
    raise
    with open('err.log', 'a') as log:
        if event == 'on_message':
            log.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

client.run(TOKEN)
