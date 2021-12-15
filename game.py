from board import DrawBoard
from time import time

import pyffish as sf

# Variant: (folder, board type, flip pieces)
VARIANTS = {'chess':            ('chess', 'checkerboard', False),
            'dragonfly':        ('chess', 'checkerboard', False),
            'extinction':       ('chess', 'checkerboard', False),
            'grand':            ('chess', 'checkerboard', False),
            'racingchess':      ('chess', 'checkerboard', False),
            'twokings':         ('chess', 'checkerboard', False),
            'chak':             ('chak', 'custom', False),
            'chennis':          ('chennis', 'custom', False),
            'makrukhouse':      ('makruk', (239, 170, 86), False),
            'mounted':          ('mounted', 'custom', False),
            'pandemonium':      ('pandemonium', [(168, 200, 224), (192, 240, 255)], True),
            'shinobimirror':    ('shinobimirror', 'checkerboard', False)
            }

class Game:
    def __init__(self, variant='chess', wplayer=None, bplayer=None, startpos=None):
        self.variant = variant
        self.wplayer = wplayer
        self.bplayer = bplayer
        self.start = time()
        self.moves = []
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

    def variants_list(self):
        return VARIANTS.keys()
    
    def age_minutes(self):
        return round((time()-self.start)/60, 2)

    def turn(self, opposite=False):
        white_to_move = "w" in self.fen.split() 
        return ["Black", "White"][white_to_move != opposite] # logical XOR

    def get_folder(self, variant):
        return VARIANTS[variant][0]

    def board_type(self, variant):
        return VARIANTS[variant][1]

    def flip_variant(self, variant):
        return VARIANTS[variant][2]

    def render(self, img_name):
        upside_down = self.turn() == 'Black'
        flip_pieces = self.flip_variant(self.variant) and upside_down
        lastmove = self.moves[-1] if self.moves else None

        board = DrawBoard(self.fen, img_name, self.get_folder(self.variant), lastmove,
                          upside_down, self.board_type(self.variant), flip_pieces)
        board.render_board()
        return img_name

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
        uci_legal_moves = sf.legal_moves(self.variant, self.fen, [])
        
        for move in uci_legal_moves:
            if sf.get_san(self.variant, self.fen, move) == san_move:
                self.moves += [move]
                break

        self.cancel_offers()
        self.update_fen()

    def legal_moves(self):
        uci_moves = sf.legal_moves(self.variant, self.fen, [])
        return [sf.get_san(self.variant, self.fen, move) for move in uci_moves]

    def get_moves(self):
        return sf.get_san_moves(self.variant, self.startpos, self.moves)

    def takeback_move(self, count):
        self.moves = self.moves[:-count]
        self.cancel_offers()
        self.update_fen()
        
    def cancel_offers(self):
        self.w_offered_draw = False
        self.b_offered_draw = False
        self.w_offered_takeback = False
        self.b_offered_takeback = False

    def update_fen(self):
        self.fen = sf.get_fen(self.variant, self.startpos, self.moves)

    def player_is_playing(self, player_name):
        return player_name in (self.wplayer, self.bplayer)
    
    def player_turn(self, player_name, opposite=False):
        white_player = self.wplayer == player_name and self.turn(opposite=opposite) == 'White'
        black_player = self.bplayer == player_name and self.turn(opposite=opposite) == 'Black'
        
        return white_player or black_player
    
    def ended(self):
        uci_legal_moves = sf.legal_moves(self.variant, self.fen, [])
        
        if len(uci_legal_moves) == 0:
            result = sf.game_result(self.variant, self.fen, [])
            turn = self.turn()
            
            if result == sf.VALUE_MATE:
                return self.turn()
            elif result == -sf.VALUE_MATE:
                return self.turn(opposite=True)
            elif result == sf.VALUE_DRAW:
                return 'Draw'

        return False
