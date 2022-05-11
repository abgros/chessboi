import PIL.Image, PIL.ImageDraw, PIL.ImageFont
from re import findall

DARK = (181, 136, 99)
LIGHT = (240, 217, 181)
GREY = (136, 136, 136)
BLACK = (33, 33, 33)
WHITE = (233, 233, 233)
GREEN = (128, 216, 48, 96)
LASTMOVE_LIGHT = (205, 210, 106)
LASTMOVE_DARK = (170, 162, 58)

ALPHABET = list("abcdefghijklmnopqrstuvwxyz")
SQ_SIZE = 100

IMGS_LOCATION = "graphics"

FONT_LOCATION = r'C:\Windows\Fonts\ARLRDBD.ttf'


class DrawBoard:
	def __init__(self, board_type, folder, flip_pieces, upside_down, intersections, invert_text, fen, lastmove):
		self.board_type = board_type
		self.folder = folder
		self.flip_pieces = flip_pieces
		self.upside_down = upside_down
		self.intersections = intersections
		self.invert_text = invert_text
		self.fen = fen
		self.lastmove = lastmove

	def flatten(self, some_list):
		output = []
		for item in some_list:
			if isinstance(item, list):
				output += self.flatten(item)
			else:
				output += [item]
		return output

	def square_to_coords(self, square, width, height):
		if self.upside_down:
			x = width - ALPHABET.index(square[0]) - 1
			y = int(square[1:]) - 1
		else:
			x = ALPHABET.index(square[0])
			y = height - int(square[1:])
		return [x*SQ_SIZE, y*SQ_SIZE]

	def get_piece_img(self, piece):
		if piece.lower() == piece:
			colour = "b"
		else:
			colour = "w"

		try:
			return PIL.Image.open(f'graphics\\{self.folder}\\{colour}{piece}.png').convert('RGBA')
		except:
			return PIL.Image.open(f'graphics\\fail.png').convert('RGBA')

	def fen_to_array(self):
		fen_array = [findall('(\d+|\+?[a-zA-Z]\~?)', i) for i in self.fen.split(' ')[0].split('[')[0].split('/')]

		for i in range(len(fen_array)):
			rank = [[""]*int(j) if j.isnumeric() else j for j in fen_array[i]]
			fen_array[i] = self.flatten(rank)

		if self.upside_down:
			fen_array = [i[::-1] for i in fen_array][::-1]

		return fen_array

	def in_hand(self):
		try:
			pocket = self.fen.split('[')[1].split(']')[0]
		except:
			return ([], [])
		blackpcs = sorted([p for p in pocket if p.islower()])
		whitepcs = sorted([p for p in pocket if p.isupper()])
		return (whitepcs, blackpcs)

	def draw_board(self, stabilise_pocket=False):
		pos = self.fen_to_array()
		b_height = len(pos)
		b_width = len(pos[0])

		white_hand, black_hand = self.in_hand()
		pocket_rows = 2 + (len(white_hand)-1) // b_height + (len(black_hand)-1) // b_height

		# To make the game clip more stable, try to keep the pocket size at an even number
		if stabilise_pocket and pocket_rows % 2 == 1:
			pocket_rows += 1

		spacer = 0
		if pocket_rows:
			spacer = round(SQ_SIZE*0.2)

		img_size = (b_width*SQ_SIZE, (b_height + pocket_rows)*SQ_SIZE + spacer)

		img = PIL.Image.new(mode='RGB', size=img_size, color=GREY)
		drw = PIL.ImageDraw.Draw(img, 'RGBA')

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
			board = PIL.Image.open(f'graphics\\{self.folder}\\board.png')
			if self.upside_down:
				board = board.rotate(180)
			img.paste(board, (0, 0))

		# HIGHLIGHTING
		if self.lastmove:
			for highlight in findall(r'[a-z]\d+', self.lastmove):
				coords = self.square_to_coords(highlight, b_width, b_height)
				highlight_coords = coords + [i+100 for i in coords]
				if self.board_type == "checkerboard":
					if sum(coords) % (SQ_SIZE*2) == 0:
						drw.rectangle(highlight_coords, fill=LASTMOVE_LIGHT)
					else:
						drw.rectangle(highlight_coords, fill=LASTMOVE_DARK)
				else:
					drw.rectangle(highlight_coords, fill=GREEN)

		# LETTERS
		font_size = SQ_SIZE*0.2
		font = PIL.ImageFont.truetype(FONT_LOCATION, round(font_size))

		ranks = [str(n+1) for n in range(b_height)]
		if not self.upside_down:
			ranks = ranks[::-1]

		files = [ALPHABET[n] for n in range(b_width)]
		if self.upside_down:
			files = files[::-1]

		if self.intersections:
			h_offset = SQ_SIZE * 0.46
			v_offset = SQ_SIZE * 0.31
			r_anchor = "mm"
			f_anchor = "mm"
		else:
			h_offset = 0
			v_offset = 0
			r_anchor = "rt"
			f_anchor = "ls"

		if self.invert_text:
			text_colour = WHITE
		else:
			text_colour = BLACK

		for i in range(b_height):
			drw.text((b_width*SQ_SIZE - font_size*0.1 - v_offset, i*SQ_SIZE + font_size*0.2 + h_offset),
					  ranks[i], fill=text_colour, font=font, anchor=r_anchor)

		for i in range(b_width):
			drw.text((i*SQ_SIZE + font_size*0.1 + h_offset, b_height*SQ_SIZE - font_size*0.1 - v_offset),
					  files[i], fill=text_colour, font=font, anchor=f_anchor)

		# PIECES
		for i in range(len(pos)):
			for j in range(len(pos[i])):
				if pos[i][j]:
					piece = self.get_piece_img(pos[i][j])
					if self.flip_pieces:
						piece = piece.rotate(180)
					img.paste(piece, (j*SQ_SIZE, i*SQ_SIZE), piece)

		# POCKET
		if pocket_rows:
			drw.rectangle([0, b_height*SQ_SIZE, b_width*SQ_SIZE, b_height*SQ_SIZE + spacer], fill=BLACK)

			white_pocket = [white_hand[i:i + b_width] for i in range(0, len(white_hand), b_width)]
			for i in range(len(white_pocket)):
				for j in range(len(white_pocket[i])):
					piece = self.get_piece_img(white_pocket[i][j])
					img.paste(piece, (j*SQ_SIZE, (i+b_height)*SQ_SIZE + spacer), piece)

			black_pocket = [black_hand[i:i + b_width] for i in range(0, len(black_hand), b_width)]
			for i in range(len(black_pocket)):
				for j in range(len(black_pocket[i])):
					piece = self.get_piece_img(black_pocket[i][j])
					img.paste(piece, (j*SQ_SIZE, (i+b_height+len(white_pocket))*SQ_SIZE + spacer), piece)

		return img

	def render_board(self, img_name):
		self.draw_board().save(img_name)

	@staticmethod
	def scale_to_fit(width, height, img):
		# resize the board the maximum amount
		prev_width, prev_height = img.size
		resize_factor = min(width / prev_width, height / prev_height)
		new_width, new_height = int(prev_width * resize_factor), int(prev_height * resize_factor)

		scaled_img = img.resize((new_width, new_height), PIL.Image.ANTIALIAS)

		# create a black background
		resized = PIL.Image.new(mode='RGB', size=(width, height), color=BLACK)

		# paste the board in the center of the black background
		offset = ((width - new_width) // 2, (height - new_height) // 2)
		resized.paste(scaled_img, offset)

		return resized