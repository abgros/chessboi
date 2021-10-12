from PIL import Image, ImageDraw, ImageFont
from re import findall

DARK = (181, 136, 99)
LIGHT = (240, 217, 181)
WHITE = (229, 229, 229)
GREY = (136, 136, 136)
BLACK = (33, 33, 33)
MED = (244, 191, 87)
GREEN = (128, 216, 48, 96)
LASTMOVE_LIGHT = (205, 210, 106)
LASTMOVE_DARK = (170, 162, 58)

ALPHABET = list("abcdefghijklmnopqrstuvwxyz")
SQ_SIZE = 100


def flatten(some_list):
    output = []
    for item in some_list:
        if isinstance(item, list): 
            output += flatten(item)
        else: 
            output += [item]
    return output


def square_to_coords(square, width, height, upside_down):
    if upside_down:
        x = width - ALPHABET.index(square[0]) - 1
        y = int(square[1:]) - 1
    else:
        x = ALPHABET.index(square[0])
        y = height - int(square[1:]) 
    return [x*SQ_SIZE, y*SQ_SIZE]


def get_piece_img(piece, folder):
    if piece.lower() == piece:
        colour = "b"
    else:
        colour = "w"
    return Image.open(f'assets\\{folder}\\{colour}{piece}.png').convert('RGBA')


def fen_to_array(fen, upside_down):
    output = [flatten([[""]*int(i) if i.isnumeric() else i for i in rank]) for rank in [findall('(\d+|\+?[a-zA-Z])', i) for i in fen.split(' ')[0].split('[')[0].split('/')]]
    if upside_down:
        output = [i[::-1] for i in output][::-1]
    return output


def in_hand(fen):
    try:
        pocket = fen.split('[')[1].split(']')[0]
    except:
        return ([], [])
    blackpcs = sorted([pc for pc in pocket if pc.lower() == pc])
    whitepcs = sorted([pc for pc in pocket if pc.lower() != pc])
    return (whitepcs, blackpcs)


def render_board(fen, img_name, folder='chess', lastmove=None, upside_down=False, board_type=None):
    pos = fen_to_array(fen, upside_down)
    b_height = len(pos)
    b_width = len(pos[0])

    white_hand, black_hand = in_hand(fen)
    pocket_rows = 2 + (len(white_hand)-1) // b_height + (len(black_hand)-1) // b_height

    spacer = 0
    if pocket_rows:
        spacer = round(SQ_SIZE*0.2)
    
    img_size = (b_width*SQ_SIZE, (b_height + pocket_rows)*SQ_SIZE + spacer)

    img = Image.new(mode='RGB', size=img_size, color=GREY)
    drw = ImageDraw.Draw(img, 'RGBA')

    # BOARD
    if board_type == "checkerboard":
        for i in range(b_height):
            for j in range(b_width):
                if (i+j) % 2 == 0:
                    drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=LIGHT)
                else:
                    drw.rectangle([j*SQ_SIZE, i*SQ_SIZE, (j+1)*SQ_SIZE, (i+1)*SQ_SIZE], fill=DARK)

    elif board_type == "custom":
        board = Image.open(f'assets\\{folder}\\board.png')
        if upside_down:
            board.rotate(180)
        img.paste(board, (0, 0))
        
    else:
        border = round(SQ_SIZE*0.01)
        drw.rectangle([0, 0, b_width*SQ_SIZE, b_height*SQ_SIZE], fill=board_type)
        for i in range(b_height-1):
            drw.rectangle([0, SQ_SIZE*(i+1) - border, b_width*SQ_SIZE, SQ_SIZE*(i+1) + border], fill=BLACK)            
        for i in range(b_height-1):
            drw.rectangle([SQ_SIZE*(i+1) - border, 0, SQ_SIZE*(i+1) + border, b_height*SQ_SIZE], fill=BLACK)                        
    
    # LETTERS
    font_size = SQ_SIZE*0.2
    font = ImageFont.truetype(r'C:\Windows\Fonts\ARLRDBD.ttf', round(font_size))

    ranks = [str(n+1) for n in range(b_height)]
    if not upside_down:
        ranks = ranks[::-1]

    files = [ALPHABET[n] for n in range(b_width)]
    if upside_down:
        files = files[::-1]
    
    for i in range(b_height):
        drw.text((b_width*SQ_SIZE - round(font_size*0.1), i*SQ_SIZE + round(font_size*0.2)), ranks[i], fill=(0, 0, 0), font=font, anchor="rt")

    for i in range(b_width):
        drw.text((i*SQ_SIZE + round(font_size*0.1), b_height*SQ_SIZE - round(font_size*0.1)), files[i], fill=(0, 0, 0), font=font, anchor="ls")

    # HIGHLIGHTING
    if lastmove:
        for highlight in findall(r'[a-z]\d+', lastmove):
            coords = square_to_coords(highlight, b_width, b_height, upside_down)
            highlight_coords = coords + [i+100 for i in coords]
            if board_type == "checkerboard":
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
                piece = get_piece_img(pos[i][j], folder)
                img.paste(piece, (j*SQ_SIZE, i*SQ_SIZE), piece)

    # POCKET
    if pocket_rows:
        drw.rectangle([0, b_height*SQ_SIZE, b_width*SQ_SIZE, b_height*SQ_SIZE + spacer], fill=BLACK)
        
        white_pocket = [white_hand[i:i + b_width] for i in range(0, len(white_hand), b_width)]
        for i in range(len(white_pocket)):
            for j in range(len(white_pocket[i])):
                piece = get_piece_img(white_pocket[i][j], folder)
                img.paste(piece, (j*SQ_SIZE, (i+b_height)*SQ_SIZE + spacer), piece)

        black_pocket = [black_hand[i:i + b_width] for i in range(0, len(black_hand), b_width)]
        for i in range(len(black_pocket)):
            for j in range(len(black_pocket[i])):
                piece = get_piece_img(black_pocket[i][j], folder)
                img.paste(piece, (j*SQ_SIZE, (i+b_height+len(white_pocket))*SQ_SIZE + spacer), piece)

    img.save(img_name)
    return img_name
