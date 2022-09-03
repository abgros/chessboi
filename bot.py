import os
import discord
import pyffish as sf
import tinydb
from re import findall
from dotenv import load_dotenv
from random import randint, sample
import asyncio

from game import Game
from engine import Engine

# ----------------------------------------------------------------
# SETUP

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
BOT_NAME = os.getenv('BOT_NAME')
ADMIN_NAME = os.getenv('ADMIN_NAME')
ENGINE_LOCATION = os.getenv('ENGINE_LOCATION')
VARIANTS_LOCATION = os.getenv('VARIANTS_LOCATION')
BOT_ID = int(os.getenv('BOT_ID'))

client = discord.Client(activity=discord.Game(name='--help'))
games_dict = {}
allowed_variants = Game.variants_list()

db = tinydb.TinyDB('saved_games.json')
for game_records in db: # only 1 entry in DB
	for channel, saved_game in game_records.items():
		game = Game()
		game.__dict__ = saved_game
		games_dict[int(channel)] = game

with open(VARIANTS_LOCATION, "r") as f:
	ini_text = f.read()
sf.load_variant_config(ini_text)
Game.set_rules(ini_text)

# ----------------------------------------------------------------


def shuffle_fen(variant):
	if variant == "chess":
		while (True):
			setup = ''.join(sample('KQRRBBNN', 8))
			if (setup.index('K') > setup.index('R')) and (setup[::-1].index('K') > setup[::-1].index('R')):
				if (setup.index('B') - setup[::-1].index('B')) % 2 == 0:
					return f"{setup.lower()}/pppppppp/8/8/8/8/PPPPPPPP/{setup} w KQkq - 0 1"

	if variant == "crazyhouse":
		while (True):
			setup = ''.join(sample('KQRRBBNN', 8))
			if (setup.index('K') > setup.index('R')) and (setup[::-1].index('K') > setup[::-1].index('R')):
				if (setup.index('B') - setup[::-1].index('B')) % 2 == 0:
					return f"{setup.lower()}/pppppppp/8/8/8/8/PPPPPPPP/{setup}[] w KQkq - 0 1"

	return sf.start_fen(variant)


def decriptive_eval(engine_eval, white_to_play):
	sides = ["White", "Black"]
	player = sides[not white_to_play]
	opp = sides[white_to_play]

	if engine_eval == "cp 0":
		return "Eval: 0.00 (dead even)"
	elif engine_eval == "mate 0":
		return f"Eval: Checkmate. **{opp}** has won!"
	elif engine_eval.split()[0] == "mate":
		moves = int(engine_eval.split()[1])
		return f"Eval: Mate in **{abs(moves)}** for **{player if moves > 0 else opp}**."
	else:
		cp = int(engine_eval.split()[1])/100 * (2 * white_to_play - 1) # invert cp if black to play
		return f"Eval: **{'{0:+.2f}'.format(cp)}** (**{sides[0] if cp > 0 else sides[1]}** is better)."


async def game_over(message, result):
	game = games_dict[message.channel.id]
	game.active = False

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
	await display_clip(message, game)

	return


async def bot_makes_move(message):
	game = games_dict[message.channel.id]

	# Get a best move from Fairy-Stockfish
	engine = Engine(ENGINE_LOCATION, VARIANTS_LOCATION, game.variant, game.bot_skill)

	if game.is_selfplay():
		await engine.allocate(threads=12, memory=4096)
		bestmove, engine_eval = await engine.analyze(game.startpos, game.moves, 60000)
	elif game.bot_skill == 20:
		await engine.allocate(threads=6, memory=1024)
		bestmove, engine_eval = await engine.analyze(game.startpos, game.moves, 30000)
	else:
		await engine.allocate(threads=1, memory=256)
		bestmove, engine_eval = await engine.analyze(game.startpos, game.moves, 5000)

	await engine.quit()

	mating_line = engine_eval.split()[0] == 'mate' and int(engine_eval.split()[1]) == -1
	# cp_losing = engine_eval.split()[0] == 'cp' and int(engine_eval.split()[1]) <= 3000
	cp_drawn = engine_eval.split()[0] == 'cp' and abs(int(engine_eval.split()[1])) <= 10

	if (cp_drawn and game.is_selfplay()):
		game.drawcount += 1
	else:
		game.drawcount = 0

	if mating_line and not game.is_selfplay():
		await message.channel.send(f"Verily, thou art a most formidable foe!")
		await message.channel.send("--resign")
		return

	if (game.drawn_game()):
		await message.channel.send("--offerdraw")
		return

	bot_move = sf.get_san(game.variant, game.fen, bestmove, True)
	eval_text = decriptive_eval(engine_eval, game.turn() == 'White')

	await message.channel.send(f"--m {bot_move} ||{eval_text}||")
	return


async def display_board(message, game_object):
	img_name = "imgs\\board_" + str(message.channel.id) + '.png'
	await message.channel.send(file=discord.File(game_object.render(img_name)))
	return


async def display_clip(message, game_object):
	clip_name = "imgs\\clip_" + str(message.channel.id) + '.mp4'
	await message.channel.send(file=discord.File(game_object.render_clip(clip_name)))
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

	# Display the following help message
	if message_text == '--help':
		output = ("**Commands:**"
				  "\n--rules [variant]"
				  "\n--fen [variant] [fen] (displays a FEN)"
				  "\n--game [variant] [@opponent] [white/black] [fen='{fen}'] [skill=(-20,20)] (starts a game)"
				  "\n--rematch"
				  "\n--move [move]"
				  "\n--premove [move]"
				  "\n--display"
				  "\n--offerdraw"
				  "\n--acceptdraw"
				  "\n--resign"
				  "\n--asktakeback"
				  "\n--accepttakeback"
				  "\n--eval"
				  "\n--clip"
				  "\nAliases: --g, --rm, --m, --pm, --d, --od, --ad --tb, --atb"
				  "\n\n**Available variants:** \n" + (', ').join(allowed_variants))

		await message.channel.send(output)
		return

	# Display the rules for a variant
	if message_text.startswith('--rules '):
		variant = message_text.split()[1]
		if variant not in allowed_variants:
			await message.channel.send("Variant not recognized.")
			return

		rules = Game.rules(variant)
		await message.channel.send(f"Rules for **{variant}**:\n```{rules}```")
		return

	# Display a position
	if message_text.startswith('--fen '):
		variant = message_text.split()[1]
		input_fen = ' '.join(message_text.split()[2:])

		# Validate variant
		if variant not in allowed_variants:
			await message.channel.send("Variant not recognized.")
			return

		# Validate FEN
		if not input_fen:
			input_fen = sf.start_fen(variant)
		else:
			# Chess960
			if input_fen == "shuffle":
				input_fen = shuffle_fen(variant)

			if sf.validate_fen(input_fen, variant, True) != sf.FEN_OK:
				await message.channel.send("Invalid FEN.")
				return

		# Create a dummy game
		position = Game(variant, startpos=sf.get_fen(variant, input_fen, []))

		await message.channel.send("**POSITION DISPLAY**")
		await display_board(message, position)

		output = (f"It's **{position.turn()}** to move."
				  f"\nFEN: {position.fen}")

		# Link to Lichess analysis board
		if variant == 'chess':
			analysis_link = 'https://lichess.org/analysis/standard/' + position.fen.replace(' ', '_')
			output += f"\nAnalyze position: {analysis_link}"

		await message.channel.send(output)
		del position
		return

	# Start a game
	if message_text.startswith('--game ') or message_text.startswith('--g '):
		# Check if game can be created
		if game and game.active:
			await message.channel.send("There is already a game going on!")
			return

		# Validate opponent
		try:
			opponent = str(await client.fetch_user(int(findall("\d+", message_text.split()[2])[0])))
		except:
			await message.channel.send("Opponent not found.")
			return

		# Validate variant
		variant = message_text.split()[1]
		if variant not in allowed_variants:
			await message.channel.send("Variant not recognized.")
			return

		# Set the starting position
		input_fen = ""
		fen_search = findall("fen=[\"|\']([^\"\']*)[\"|\']", message_text)
		if fen_search:
			input_fen = fen_search[0]

			if not input_fen:
				input_fen = sf.start_fen(variant)
			elif input_fen == "shuffle": # Shuffle back rank pieces
				input_fen = shuffle_fen(variant)

			if sf.validate_fen(input_fen, variant, True) == sf.FEN_OK:
				start_fen = sf.get_fen(variant, input_fen, [])
			else:
				await message.channel.send("Invalid FEN.")
				return
		else:
			start_fen = sf.start_fen(variant)

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
		await message.channel.send(f"Game started of: **{game.variant}**"
								   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**")
		await display_board(message, game)

		if game.player_turn(BOT_NAME):
			await bot_makes_move(message)
		return

	# Start a rematch
	if message_text in ('--rematch', '--rm'):
		if game and game.active:
			await message.channel.send("There is already a game going on!")
			return

		# Check if player was in previous match
		if not (game and username in (game.wplayer, game.bplayer)):
			await message.channel.send("You must Match before you can Rematch.")
			return

		# Create a new game based on the last one to be played
		prev_bot_skill = game.bot_skill
		games_dict[message.channel.id] = Game(game.variant, game.bplayer, game.wplayer, game.startpos) # Reverse black & white
		game = games_dict[message.channel.id]
		game.bot_skill = prev_bot_skill

		await message.channel.send(f"Game started of: **{game.variant}**"
								   f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**")
		await display_board(message, game)

		if game.player_turn(BOT_NAME):
			await bot_makes_move(message)
		return

	# Make a move
	if message_text.startswith('--move ') or message_text.startswith('--m '):
		# Check if move can be made
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		if not game.player_turn(username):
			await message.channel.send("It's not your turn!")
			return

		move = message_text.split()[1]
		if not (username == BOT_NAME):
			move = game.closest_san(move) # bot will always make a perfectly formatted move

		if not move:
			await message.channel.send("Invalid move.")
			return

		game.make_move(move)

		# Check if game has ended
		if game.ended():
			await game_over(message, game.ended())
			return

		output = f"**{game.turn(opposite=True)}** made move: **{move}**"

		# Execute premove
		if game.premove:
			premove = game.closest_san(game.premove)
			game.premove = None

			# Check if premove can be made
			if not premove:
				output += "\nPremove not made."
			else:
				game.make_move(premove)
				if game.ended():
					await game_over(message, game.ended())
					return
				output += f"\n**{game.turn(opposite=True)}** premoved: {premove}"

		await message.channel.send(output)
		await display_board(message, game)

		# Bot move (bot doesn't premove)
		if game.player_turn(BOT_NAME):
			await bot_makes_move(message)
		return

	# Prepare a premove
	if message_text.startswith('--premove') or message_text.startswith('--pm'):
		await asyncio.sleep(2) # otherwise stuff breaks

		# Check if premove can be made
		if not (game and game.active):
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

	# Display game info
	if message_text in ('--display', '--d'):
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		output = (f"Variant: **{game.variant}**"
				  f"{chr(10) + 'Custom start: **' + game.startpos + '**' if game.custom_fen else ''}" # chr(10) is '\n'
				  f"{chr(10) + 'Bot level: **' + str(game.bot_skill) + '**' if game.player_is_playing(BOT_NAME) else ''}"
				  f"\nPosition: **{game.fen}**"
				  f"\nMoves so far: {' '.join(game.get_moves())}"
				  f"\nOpponents: **{game.wplayer}** vs **{game.bplayer}**"
				  f"\nIt's **{game.turn()}** to move."
				  f"\nLegal moves: {' '.join(game.legal_moves()[:100])}"
				  f"{' (truncated)' if len(game.legal_moves()) > 100 else ''}"
				  f"\n*(Game started {game.age_minutes()} minutes ago.)*")

		await display_board(message, game)
		await message.channel.send(output)
		return

	# Resign an ongoing game
	if message_text == '--resign':
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		if username == BOT_NAME:
			await game_over(message, game.turn(opposite=True)) # bot only resigns on his own turn
			return

		if username == game.wplayer:
			await game_over(message, "Black")
			return

		if username == game.bplayer:
			await game_over(message, "White")
			return

		await message.channel.send("You're not playing!")
		return

	# Offer a draw
	if message_text in ('--offerdraw', '--od'):
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		if username == game.wplayer:
			if game.w_offered_draw:
				await message.channel.send("You already offered a draw.")
				return

			game.w_offered_draw = True

			await message.channel.send("White offers a draw!")

			if game.player_is_playing(BOT_NAME):
				await asyncio.sleep(1)
				await message.channel.send("--acceptdraw")

			return

		if username == game.bplayer:
			if game.b_offered_draw:
				await message.channel.send("You already offered a draw.")
				return

			game.b_offered_draw = True

			await message.channel.send("Black offers a draw!")

			if game.player_is_playing(BOT_NAME):
				await message.channel.send("--acceptdraw")

			return

		await message.channel.send("You're not playing!")
		return

	# Accept a draw
	if message_text in ('--acceptdraw', '--ad'):
		if not (game and game.active):
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

	# Ask for a takeback
	if message_text in ('--asktakeback', '--tb'):
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		if username == game.wplayer:
			if game.w_offered_takeback:
				await message.channel.send("You already offered a takeback.")
				return

			game.w_offered_takeback = True
			await message.channel.send("White asks for a takeback!")

			if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
				await asyncio.sleep(1)
				await message.channel.send("--accepttakeback")

			return

		if username == game.bplayer:
			if game.b_offered_takeback:
				await message.channel.send("You already offered a takeback.")
				return

			game.b_offered_takeback = True
			await message.channel.send("Black asks for a takeback!")

			if game.player_is_playing(BOT_NAME) and username != BOT_NAME:
				await message.channel.send("--accepttakeback")

			return

		await message.channel.send("You're not playing!")
		return

	# Accept a takeback
	if message_text in ('--accepttakeback', '--atb'):
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		if username not in (game.wplayer, game.bplayer):
			await message.channel.send("You're not playing!")
			return

		if username == game.wplayer and game.b_offered_takeback:
			game.takeback_move(1 + (game.turn() == "Black")) # take back requester's last move

			await message.channel.send(f"White has granted a takeback: Black's last move has been undone.")
			return

		if username == game.bplayer and game.w_offered_takeback:
			game.takeback_move(1 + (game.turn() == "White")) # take back requester's last move

			await message.channel.send(f"Black has granted a takeback: White's last move has been undone.")
			return

		await message.channel.send("No takeback requests active.")
		return

	# Evaluate the current board position
	if message_text == '--eval':
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return

		# Get a best move from Fairy-Stockfish
		engine = Engine(ENGINE_LOCATION, VARIANTS_LOCATION, game.variant, 20)
		if username == ADMIN_NAME:
			await engine.allocate(threads=6, memory=2048)
			bestmove, engine_eval = await engine.analyze(game.startpos, game.moves, 30000)
		else:
			await engine.allocate(threads=1, memory=256)
			bestmove, engine_eval = await engine.analyze(game.startpos, game.moves, 5000)
		await engine.quit()

		await message.channel.send(f"||{decriptive_eval(engine_eval, game.turn() == 'White')}||")
		return

	# Create a clip
	if message_text == '--clip':
		if not (game and game.active):
			await message.channel.send("No game is active.")
			return
		await display_clip(message, game)
		return

	# ---- Admin Commands ----

	# Save current games
	if message_text == '--save' and username == ADMIN_NAME:
		db.truncate()
		db.insert({key: games_dict[key].__dict__ for key in games_dict}) # convert games to dict
		await message.channel.send("Saved current games.")
		return

	# Game debug info
	if message_text == '--repr' and username == ADMIN_NAME:
		if game:
			await message.channel.send(game.__dict__)
		return

	# Prematurely end a game
	if message_text == '--end' and username == ADMIN_NAME:
		await game_over(message, "Draw")
		return

	# Force bot to make a move
	if message_text == '--botmove' and username == ADMIN_NAME:
		if game and game.active:
			await bot_makes_move(message)
		else:
			await message.channel.send("No game is active.")

	# Start a selfplay match
	if message_text.startswith('--selfplay ') and username == ADMIN_NAME:
		variant = message_text.split()[1]
		input_fen = ' '.join(message_text.split()[2:])
		await message.channel.send(f"--game {variant} <@!{BOT_ID}> skill=20 fen='{input_fen}'")
		return

	if str(client.user.id) in message_text and message.author != client.user:
		await message.channel.send("hello! :)")
		return


@client.event
async def on_error(event, *args, **kwargs):
	raise

client.run(TOKEN)