from gen_board import render_board
from re import findall
from dotenv import load_dotenv
from time import time

import os
import discord
import pyffish as sf


class Game():
    def __init__(self, channel, wplayer, bplayer, variant, moves):
        self.channel = channel
        self.wplayer = wplayer
        self.bplayer = bplayer
        self.variant = variant
        self.moves = moves
        self.start = time()
        self.w_offered_draw = False
        self.b_offered_draw = False
        
    def age_minutes(self):
        return round((time()-self.start)/60, 2)

    def turn(self):
        return ["White", "Black"][len(self.moves) % 2]

    def piece_type(self):
        sets_dict = {
            'chess': 'chess',
            'crazyhouse': 'chess',
            'grand': 'chess',
            'extinction': 'chess',

            'chennis': 'chennis',
            'ridgerelay': 'ridgerelay'
        }
        return sets_dict[self.variant]

    def board_type(self):
        boards_dict = {
            'chess': None,
            'crazyhouse': None,
            'grand': None,
            'extinction': None,
            'grand': None,

            'chennis': (244, 191, 87),
            'ridgerelay': (153, 174, 194)
        }
        return boards_dict[self.variant]

    def render(self, img_name):
        upside_down = self.turn() == "Black"
        lastmove = None
        if self.moves:
            lastmove = self.moves[-1]
        render_board(self.fen(), img_name, self.piece_type(), lastmove, upside_down, self.board_type())
        return img_name
    
    def make_move(self, san_move):
        legal_moves = sf.legal_moves(self.variant, self.fen(), [])
        for move in legal_moves:
            if sf.get_san(self.variant, self.fen(), move) == san_move:
                self.moves += [move]
        self.cancel_offers()

    def legal_moves(self):
        uci_moves = sf.legal_moves(self.variant, self.fen(), [])
        return [sf.get_san(self.variant, self.fen(), move) for move in uci_moves]

    def get_moves(self):
        return sf.get_san_moves(self.variant, sf.start_fen(self.variant), self.moves)

    def cancel_offers(self):
        self.w_offered_draw = False
        self.b_offered_draw = False

    def fen(self):
        return sf.get_fen(self.variant, sf.start_fen(self.variant), self.moves)
    
    def ended(self):
        if len(self.legal_moves()) == 0:
            result = sf.game_result(self.variant, sf.start_fen(self.variant), self.moves)
            if result == sf.VALUE_MATE:
                return "Win"
            elif result == sf.VALUE_DRAW:
                return "Draw"
            elif result == -sf.VALUE_MATE:
                return "Loss"
        return False
