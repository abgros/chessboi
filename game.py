from variant import Variant
from clip import GameClip
from board import DrawBoard
from time import time
from re import findall

import pyffish as sf

VARIANTS = {
			'backrank':			Variant(),
			'cetus':			Variant(folder='cetus', board_type='custom', intersections=True),
			'chak':				Variant(folder='chak', board_type='custom'),
			'checkmateless':	Variant(),
			'chennis':			Variant(folder='chennis', board_type='custom'),
			'chess':			Variant(rules='Ordinary chess.'),
			'chessvshp':		Variant(),
			'crazyhouse':		Variant(rules='Chess but you can AIRDROP pieces?!?!?!11 (It\'s \'crazy\')'),
			'cwda':				Variant(folder='cwda'),
			'dragonfly':		Variant(),
			'extinction':		Variant(rules='Win by capturing every piece of a certain type (eg. 1 queen or 2 bishops).'),
			'grand':			Variant(rules='Chess but bigger. Hawk = B+N, Elephant = R+N. Pawns promote on the 8th rank to a captured piece.'),
			'kamikazerooks':	Variant(),
			'makhouse':			Variant(folder='makruk', board_type=(239, 170, 86)),
			'mounted':			Variant(folder='mounted', board_type='custom'),
			'ordavsempire':		Variant(folder='ordavsempire', rules='Orda vs Empire army'),
			'pandemonium':		Variant(folder='pandemonium', board_type=[(168, 200, 224), (192, 240, 255)]),
			'racingchess':		Variant(),
			'shinobimirror':	Variant(folder='shinobimirror'),
			'stardust':			Variant(folder='stardust', board_type='custom', invert_text=True),
			'twokings':			Variant()
			}

class Game:
	def __init__(self, variant='chess', wplayer=None, bplayer=None, startpos=None):
		self.variant = variant
		self.wplayer = wplayer
		self.bplayer = bplayer
		self.start = time()
		self.moves = []
		self.drawcount = 0
		self.w_offered_draw = False
		self.b_offered_draw = False
		self.w_offered_takeback = False
		self.b_offered_takeback = False
		self.bot_skill = 0
		self.premove = None
		self.custom_fen = startpos and (startpos != sf.start_fen(variant))
		self.startpos = startpos if self.custom_fen else sf.start_fen(variant)
		self.fen = self.startpos
		self.active = True

	@staticmethod
	def variants_list():
		return sorted(VARIANTS.keys())

	@staticmethod
	def set_rules(ini_text):
		for definition in ini_text.split('\n\n'):
			variant_name = findall("\[(.+?)[:|\]]", definition)[0]
			VARIANTS[variant_name].rules = definition

	@staticmethod
	def rules(variant):
		return VARIANTS[variant].rules

	def age_minutes(self):
		return round((time()-self.start)/60, 2)

	def turn(self, opposite=False):
		white_to_move = "w" in self.fen.split()
		return ["Black", "White"][white_to_move != opposite] # if opposite is True, white_to_move is flipped

	def render(self, img_name):
		flip_pieces = VARIANTS[self.variant].flip_pieces and upside_down
		upside_down = self.turn() == "Black"
		lastmove = self.moves[-1] if self.moves else None
		folder = VARIANTS[self.variant].folder
		board_type = VARIANTS[self.variant].board_type
		intersections = VARIANTS[self.variant].intersections

		DrawBoard(board_type, folder, flip_pieces, upside_down, intersections,
				self.fen, lastmove).render_board(img_name)

		return img_name

	def render_clip(self, clip_name):
		WIDTH = 800
		HEIGHT = 1000
		FPS = 2

		clip = GameClip(WIDTH, HEIGHT, FPS, clip_name)
		# upside_down and flip_pieces will be false as the board is always from White's view
		flip_pieces = upside_down = lastmove = False
		board_type = VARIANTS[self.variant].board_type
		folder = VARIANTS[self.variant].folder
		intersections = VARIANTS[self.variant].intersections

		# add end position
		if len(self.moves) > 0:
			board_img = DrawBoard(board_type, folder, flip_pieces, upside_down, intersections,
								self.fen, self.moves[-1]).draw_board(stabilise_pocket=True)

			frame = DrawBoard.scale_to_fit(WIDTH, HEIGHT, board_img)
			clip.add_img(frame, frames=2)

		# add start position
		curr_fen = self.startpos
		board_img = DrawBoard(board_type, folder, flip_pieces, upside_down, intersections,
							  curr_fen, lastmove).draw_board(stabilise_pocket=True)

		frame = DrawBoard.scale_to_fit(WIDTH, HEIGHT, board_img)
		clip.add_img(frame, frames=1)

		# loop over each move and repeat
		for i in range(len(self.moves)):
			lastmove = self.moves[i]
			curr_fen = sf.get_fen(self.variant, curr_fen, [lastmove], True)

			board_img = DrawBoard(board_type, folder, flip_pieces, upside_down, intersections,
								  curr_fen, lastmove).draw_board(stabilise_pocket=True)

			frame = DrawBoard.scale_to_fit(WIDTH, HEIGHT, board_img)

			clip.add_img(frame, frames=1)

		# save the clip
		clip.save()
		return clip_name

	def closest_san(self, input_move):
		legal = self.legal_moves() # All legal moves, in SAN format

		match_casesens = [m for m in legal if m == input_move]
		if len(match_casesens) == 1:
			return match_casesens[0]

		prefix_casesens = [m for m in legal if m.startswith(input_move)]
		if len(prefix_casesens) == 1:
			return prefix_casesens[0]

		match_lower = [m for m in legal if m.lower() == input_move.lower()]
		if len(match_lower) == 1:
			return match_lower[0]

		prefix_lower = [m for m in legal if m.lower().startswith(input_move.lower())]
		if len(prefix_lower) == 1:
			return prefix_lower[0]

		return None

	def make_move(self, san_move):
		uci_legal_moves = sf.legal_moves(self.variant, self.fen, [], True)

		for move in uci_legal_moves:
			if sf.get_san(self.variant, self.fen, move, True) == san_move:
				self.moves += [move]
				break

		self.cancel_offers()
		self.fen = sf.get_fen(self.variant, self.fen, [move], True)

	def legal_moves(self):
		uci_moves = sf.legal_moves(self.variant, self.fen, [], True)
		return [sf.get_san(self.variant, self.fen, move, True) for move in uci_moves]

	def get_moves(self):
		return sf.get_san_moves(self.variant, self.startpos, self.moves, True)

	def takeback_move(self, count):
		self.moves = self.moves[:-count]
		self.cancel_offers()
		self.fen = sf.get_fen(self.variant, self.startpos, self.moves, True)

	def cancel_offers(self):
		self.w_offered_draw = False
		self.b_offered_draw = False
		self.w_offered_takeback = False
		self.b_offered_takeback = False

	def player_is_playing(self, player_name):
		return player_name in (self.wplayer, self.bplayer)

	def drawn_game(self):
		return self.drawcount >= 10 and len(self.moves) >= 80

	def is_selfplay(self):
		return self.wplayer == self.bplayer

	def player_turn(self, player_name, opposite=False):
		white_player = self.wplayer == player_name and self.turn(opposite=opposite) == 'White'
		black_player = self.bplayer == player_name and self.turn(opposite=opposite) == 'Black'

		return white_player or black_player

	def ended(self):
		uci_legal_moves = sf.legal_moves(self.variant, self.fen, [], True)

		if (len(sf.legal_moves(self.variant, self.startpos, self.moves, True)) == 0
			or sf.is_optional_game_end(self.variant, self.startpos, self.moves, True)[0]
			or sf.is_immediate_game_end(self.variant, self.startpos, self.moves, True)[0]
			or all(sf.has_insufficient_material(self.variant, self.startpos, self.moves, True))):

			result = sf.game_result(self.variant, self.startpos, self.moves, True)
			turn = self.turn()

			if result == sf.VALUE_MATE:
				return self.turn()
			elif result == -sf.VALUE_MATE:
				return self.turn(opposite=True)
			elif result == sf.VALUE_DRAW:
				return 'Draw'

		return False