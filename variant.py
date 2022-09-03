class Variant:
	def __init__(self, folder='chess', board_type='checkerboard', flip_pieces=False, intersections=False, invert_text=False, rules=''):
		self.folder = folder
		self.board_type = board_type
		self.flip_pieces = flip_pieces
		self.intersections = intersections
		self.invert_text = invert_text
		self.rules = rules