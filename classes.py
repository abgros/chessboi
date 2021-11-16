from gen_board import render_board
from time import time

import pyffish as sf


class Game():
    def __init__(self, variant, wplayer=None, bplayer=None):
        self.variant = variant
        self.wplayer = wplayer
        self.bplayer = bplayer
        self.moves = []
        self.fen = sf.start_fen(self.variant)
        self.start = time()
        self.w_offered_draw = False
        self.b_offered_draw = False
        self.w_offered_takeback = False
        self.b_offered_takeback = False
        
    def age_minutes(self):
        return round((time()-self.start)/60, 2)

    def turn(self):
        return ["Black", "White"]["w" in self.fen.split()]

    def get_folder(self, variant):
        folder_dict = {
            'chess': 'chess',
            'extinction': 'chess',
            'twokings': 'chess',
            'racingchess': 'chess',
            'checklesszh': 'chess',
            'dragonfly': 'chess',

            'pandemonium': 'pandemonium',
            'chennis': 'chennis',
            'mounted': 'mounted',
            'shinobimirror': 'shinobimirror',
            'chak': 'chak'
        }
        return folder_dict[variant]

    def board_type(self, variant):
        boards_dict = {
            'chess': 'checkerboard',
            'extinction': 'checkerboard',
            'twokings': 'checkerboard',
            'racingchess': 'checkerboard',
            'checklesszh': 'checkerboard',
            'dragonfly': 'checkerboard',
            'shinobimirror': 'checkerboard',

            'pandemonium': [(168, 200, 224), (192, 240, 255)],
            'chennis': 'custom',
            'chak': 'custom',
            'mounted': [(153, 174, 194), (97, 122, 142)]
        }
        return boards_dict[variant]

    def flip_variant(self, variant):
        flip_variants_list = ['pandemonium']
        return (variant in flip_variants_list)

    def render(self, img_name):
        upside_down = self.turn() == "Black"
        flip_pieces = self.flip_variant(self.variant) and upside_down
        lastmove = self.moves[-1] if self.moves else None
        
        render_board(self.fen, img_name, self.get_folder(self.variant), lastmove,
                     upside_down, self.board_type(self.variant), flip_pieces)
        return img_name

    def closest_san(self, input_move):
        legal = self.legal_moves()
        legal_lower = [move.lower() for move in legal]
        input_lower = input_move.lower()

        # Try to find a unique move, case insensitive
        if sum(i.startswith(input_lower) for i in legal_lower) == 1:
            return legal[legal_lower.index([i for i in legal_lower if i.startswith(input_lower)][0])]

        # Try to find a unique move, original case
        if sum(i.startswith(input_move) for i in legal) == 1:
            return legal[legal.index([i for i in legal if i.startswith(input_move)][0])]

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
        return sf.get_san_moves(self.variant, sf.start_fen(self.variant), self.moves)

    def takeback_move(self):
        self.moves = self.moves[:-2]
        self.cancel_offers()
        self.update_fen()
        
    def cancel_offers(self):
        self.w_offered_draw = False
        self.b_offered_draw = False
        self.w_offered_takeback = False
        self.b_offered_takeback = False

    def update_fen(self):
        self.fen = sf.get_fen(self.variant, sf.start_fen(self.variant), self.moves)
    
    def ended(self):
        uci_legal_moves = sf.legal_moves(self.variant, self.fen, [])
        
        if len(uci_legal_moves) == 0:
            result = sf.game_result(self.variant, self.fen, [])
            if result == sf.VALUE_MATE:
                return "Win"
            elif result == sf.VALUE_DRAW:
                return "Draw"
            elif result == -sf.VALUE_MATE:
                return "Loss"
        return False
