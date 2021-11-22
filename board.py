from PIL import Image, ImageDraw, ImageFont
from re import findall

DARK = (181, 136, 99)
LIGHT = (240, 217, 181)
GREY = (136, 136, 136)
BLACK = (33, 33, 33)
GREEN = (128, 216, 48, 96)
LASTMOVE_LIGHT = (205, 210, 106)
LASTMOVE_DARK = (170, 162, 58)

ALPHABET = list("abcdefghijklmnopqrstuvwxyz")
SQ_SIZE = 100

FONT_LOCATION = r'C:\Windows\Fonts\ARLRDBD.ttf'


class DrawBoard:
    def __init__(self, fen, img_name, folder='chess', lastmove=None, upside_down=False, board_type=None, flip_pieces=False):
        self.fen = fen
        self.img_name = img_name
        self.folder = folder
        self.lastmove = lastmove
        self.upside_down = upside_down
        self.board_type = board_type
        self.flip_pieces = flip_pieces
    
    def flatten(self, some_list):
        output = []
        for item in some_list:
            if isinstance(item, list): 
                output += self.flatten(item)
            else: 
                output += [item]
        return output

    def square_to_coords(self, square, width, height, upside_down):
        if upside_down:
            x = width - ALPHABET.index(square[0]) - 1
            y = int(square[1:]) - 1
        else:
            x = ALPHABET.index(square[0])
            y = height - int(square[1:]) 
        return [x*SQ_SIZE, y*SQ_SIZE]

    def get_piece_img(self, piece, folder):
        if piece.lower() == piece:
            colour = "b"
        else:
            colour = "w"
        return Image.open(f'assets\\{folder}\\{colour}{piece}.png').convert('RGBA')

    def fen_to_array(self, fen, upside_down):
        output = [self.flatten([[""]*int(i) if i.isnumeric() else i for i in rank]) for rank in [findall('(\d+|\+?[a-zA-Z])', i) for i in fen.split(' ')[0].split('[')[0].split('/')]]
        if upside_down:
            output = [i[::-1] for i in output][::-1]
        return output

    def in_hand(self, fen):
        try:
            pocket = fen.split('[')[1].split(']')[0]
        except:
            return ([], [])
        blackpcs = sorted([p for p in pocket if p.lower() == p])
        whitepcs = sorted([p for p in pocket if p.lower() != p])
        return (whitepcs, blackpcs)

    def render_board(self):
        pos = self.fen_to_array(self.fen, self.upside_down)
        b_height = len(pos)
        b_width = len(pos[0])

        white_hand, black_hand = self.in_hand(self.fen)
        pocket_rows = 2 + (len(white_hand)-1) // b_height + (len(black_hand)-1) // b_height

        spacer = 0
        if pocket_rows:
            spacer = round(SQ_SIZE*0.2)
        
        img_size = (b_width*SQ_SIZE, (b_height + pocket_rows)*SQ_SIZE + spacer)

        img = Image.new(mode='RGB', size=img_size, color=GREY)
        drw = ImageDraw.Draw(img, 'RGBA')

        # BOARD
        if self.board_type == "checkerboard": # chess style checkerboard
            for i in range(b_height):
                for j in range(b_width):
                    if (i+j) % 2 == 0:
                        drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=LIGHT)
                    else:
                        drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=DARK)

        elif isinstance(self.board_type, list): # checkerboard with custom colours
            for i in range(b_height):
                for j in range(b_width):
                    if (i+j) % 2 == 0:
                        drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=self.board_type[0])
                    else:
                        drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=self.board_type[1])
            
        elif isinstance(self.board_type, tuple): # shogi style board with a custom colour
            border = round(SQ_SIZE*0.01)
            drw.rectangle([0, 0, b_width*SQ_SIZE, b_height*SQ_SIZE], fill=self.board_type)
            for i in range(b_height-1):
                drw.rectangle([0, SQ_SIZE*(i+1) - border, b_width*SQ_SIZE, SQ_SIZE*(i+1) + border], fill=BLACK)            
            for i in range(b_height-1):
                drw.rectangle([SQ_SIZE*(i+1) - border, 0, SQ_SIZE*(i+1) + border, b_height*SQ_SIZE], fill=BLACK)                        

        else: # custom image
            board = Image.open(f'assets\\{self.folder}\\board.png')
            if self.upside_down:
                board = board.rotate(180)
            img.paste(board, (0, 0))
        
        # LETTERS
        font_size = SQ_SIZE*0.2
        font = ImageFont.truetype(FONT_LOCATION, round(font_size))

        ranks = [str(n+1) for n in range(b_height)]
        if not self.upside_down:
            ranks = ranks[::-1]

        files = [ALPHABET[n] for n in range(b_width)]
        if self.upside_down:
            files = files[::-1]
        
        for i in range(b_height):
            drw.text((b_width*SQ_SIZE - round(font_size*0.1), i*SQ_SIZE + round(font_size*0.2)), ranks[i], fill=(0, 0, 0), font=font, anchor="rt")

        for i in range(b_width):
            drw.text((i*SQ_SIZE + round(font_size*0.1), b_height*SQ_SIZE - round(font_size*0.1)), files[i], fill=(0, 0, 0), font=font, anchor="ls")

        # HIGHLIGHTING
        if self.lastmove:
            for highlight in findall(r'[a-z]\d+', self.lastmove):
                coords = self.square_to_coords(highlight, b_width, b_height, self.upside_down)
                highlight_coords = coords + [i+100 for i in coords]
                if self.board_type != "checkerboard":
                    drw.rectangle(highlight_coords, fill=GREEN)
                else:
                    if sum(coords) % (SQ_SIZE*2) == 0:
                        drw.rectangle(highlight_coords, fill=LASTMOVE_LIGHT)
                    else:
                        drw.rectangle(highlight_coords, fill=LASTMOVE_DARK)

        # PIECES
        for i in range(len(pos)):
            for j in range(len(pos[i])):
                if pos[i][j]:
                    piece = self.get_piece_img(pos[i][j], self.folder)
                    if self.flip_pieces:
                        piece = piece.rotate(180)
                    img.paste(piece, (j*SQ_SIZE, i*SQ_SIZE), piece)

        # POCKET
        if pocket_rows:
            drw.rectangle([0, b_height*SQ_SIZE, b_width*SQ_SIZE, b_height*SQ_SIZE + spacer], fill=BLACK)
            
            white_pocket = [white_hand[i:i + b_width] for i in range(0, len(white_hand), b_width)]
            for i in range(len(white_pocket)):
                for j in range(len(white_pocket[i])):
                    piece = self.get_piece_img(white_pocket[i][j], self.folder)
                    img.paste(piece, (j*SQ_SIZE, (i+b_height)*SQ_SIZE + spacer), piece)

            black_pocket = [black_hand[i:i + b_width] for i in range(0, len(black_hand), b_width)]
            for i in range(len(black_pocket)):
                for j in range(len(black_pocket[i])):
                    piece = self.get_piece_img(black_pocket[i][j], self.folder)
                    img.paste(piece, (j*SQ_SIZE, (i+b_height+len(white_pocket))*SQ_SIZE + spacer), piece)

        img.save(self.img_name)
        return self.img_name
